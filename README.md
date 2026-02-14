# Lucidly

## Setup Instructions

1.  **Install root dependencies**:
    ```bash
    npm install
    ```

2.  **Install Frontend dependencies**:
    ```bash
    cd frontend && bun install && cd ..
    ```

3.  **Install Backend dependencies**:
    ```bash
    cd backend && uv sync && cd ..
    ```

## Running the Project

To start the development server for both the frontend and backend concurrently:

```bash
bun run dev
```

This command will:
- Start the backend server on `http://0.0.0.0:8000`
- Start the frontend development server on `http://localhost:3000`
