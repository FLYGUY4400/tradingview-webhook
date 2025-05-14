import os
from pathlib import Path
from dotenv import load_dotenv

def load_environment():
    # Find the .env file by looking in the current directory and parent directories
    current_dir = Path(__file__).resolve().parent
    env_path = None
    
    while current_dir.parent != current_dir:  # Stop at root directory
        possible_env = current_dir / '.env'
        if possible_env.exists():
            env_path = possible_env
            break
        current_dir = current_dir.parent
    
    if env_path is None:
        raise ValueError("Could not find .env file")
        
    # Load the environment variables
    load_dotenv(env_path)
    
    # Validate required environment variables
    required_vars = ['TOPSTEPX_SESSION_TOKEN', 'TOPSTEPX_API_KEY', 'TOPSTEPX_USERNAME']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
