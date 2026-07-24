import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()


def test_register_user():
    response = client.post(
        "/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "testpass123"
        }
    )
    assert response.status_code == 201
    assert response.json()["username"] == "testuser"
    assert response.json()["email"] == "test@example.com"


def test_register_duplicate_username():
    client.post(
        "/register",
        json={
            "username": "testuser",
            "email": "test1@example.com",
            "password": "testpass123"
        }
    )
    response = client.post(
        "/register",
        json={
            "username": "testuser",
            "email": "test2@example.com",
            "password": "testpass123"
        }
    )
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


def test_login():
    client.post(
        "/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "testpass123"
        }
    )
    response = client.post(
        "/token",
        data={"username": "testuser", "password": "testpass123"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"


def test_login_wrong_password():
    client.post(
        "/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "testpass123"
        }
    )
    response = client.post(
        "/token",
        data={"username": "testuser", "password": "wrongpass"}
    )
    assert response.status_code == 401


def get_auth_header():
    client.post(
        "/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "testpass123"
        }
    )
    response = client.post(
        "/token",
        data={"username": "testuser", "password": "testpass123"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_task():
    headers = get_auth_header()
    response = client.post(
        "/tasks",
        json={
            "title": "Test Task",
            "description": "This is a test",
            "priority": "high"
        },
        headers=headers
    )
    assert response.status_code == 201
    assert response.json()["title"] == "Test Task"
    assert response.json()["completed"] is False


def test_get_tasks():
    headers = get_auth_header()
    client.post(
        "/tasks",
        json={"title": "Task 1", "description": "First task"},
        headers=headers
    )
    client.post(
        "/tasks",
        json={"title": "Task 2", "description": "Second task"},
        headers=headers
    )
    
    response = client.get("/tasks", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_task_by_id():
    headers = get_auth_header()
    create_response = client.post(
        "/tasks",
        json={"title": "Test Task", "description": "Test description"},
        headers=headers
    )
    task_id = create_response.json()["id"]
    
    response = client.get(f"/tasks/{task_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["title"] == "Test Task"


def test_update_task():
    headers = get_auth_header()
    create_response = client.post(
        "/tasks",
        json={"title": "Original Title", "description": "Original description"},
        headers=headers
    )
    task_id = create_response.json()["id"]
    
    response = client.put(
        f"/tasks/{task_id}",
        json={"title": "Updated Title", "completed": True},
        headers=headers
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Title"
    assert response.json()["completed"] is True


def test_delete_task():
    headers = get_auth_header()
    create_response = client.post(
        "/tasks",
        json={"title": "Task to Delete", "description": "Will be deleted"},
        headers=headers
    )
    task_id = create_response.json()["id"]
    
    response = client.delete(f"/tasks/{task_id}", headers=headers)
    assert response.status_code == 204
    
    get_response = client.get(f"/tasks/{task_id}", headers=headers)
    assert get_response.status_code == 404


def test_search_tasks():
    headers = get_auth_header()
    client.post(
        "/tasks",
        json={"title": "Python programming", "description": "Learn Python"},
        headers=headers
    )
    client.post(
        "/tasks",
        json={"title": "Java programming", "description": "Learn Java"},
        headers=headers
    )
    
    response = client.get("/tasks/search/?query=Python", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert "Python" in response.json()[0]["title"]


def test_unauthorized_access():
    response = client.get("/tasks")
    assert response.status_code == 401


def test_get_current_user():
    headers = get_auth_header()
    response = client.get("/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["username"] == "testuser"
