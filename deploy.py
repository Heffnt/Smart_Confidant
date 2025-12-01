"""
Smart Confidant - Unified Cloud Deployment Script
Builds, pushes, and deploys the application to GCP Cloud Run, Azure Container Apps, or AWS App Runner.
"""

import subprocess
import sys
import os

# ============================================================================
# Configuration
# ============================================================================

DOCKER_USER = "heffnt"
DOCKER_IMAGE = "smart_confidant"
DOCKER_TAG = "latest"
FULL_IMAGE_NAME = f"{DOCKER_USER}/{DOCKER_IMAGE}:{DOCKER_TAG}"
LOCAL_PORT = 8080
APP_ENTRYPOINT = os.path.join(os.path.dirname(__file__), "app.py")

# Pre-select menu option (1-5). Set to None to prompt the user interactively.
DEFAULT_CHOICE = 5

# Cloud service names (used when deploying)
SERVICE_NAME = "smart-confidant"
REGION_GCP = "us-central1"
REGION_AZURE = "eastus"
REGION_AWS = "us-east-1"

# ============================================================================
# Helper Functions
# ============================================================================

def run_cmd(cmd, check=True):
    """Run a shell command and return success status."""
    print(f"  Running: {cmd}")
    result = subprocess.run(cmd, shell=True)
    if check and result.returncode != 0:
        print(f"  Command failed with exit code {result.returncode}")
        return False
    return result.returncode == 0

def check_tool(tool_name):
    """Check if a CLI tool is installed."""
    result = subprocess.run(
        f"{tool_name} --version",
        shell=True,
        capture_output=True,
        text=True
    )
    return result.returncode == 0

# ============================================================================
# Build & Push
# ============================================================================

def build_image():
    """Build Docker image locally."""
    print("\n[1/2] Building Docker image...")
    return run_cmd(f"docker build -t {FULL_IMAGE_NAME} .")

def push_image():
    """Push Docker image to Docker Hub."""
    print("\n[2/2] Pushing to Docker Hub...")
    print(f"  Image: {FULL_IMAGE_NAME}")
    return run_cmd(f"docker push {FULL_IMAGE_NAME}")


def run_local():
    """Run app.py locally for quick iteration without deploying."""
    print("\n--- Running locally ---")
    env = os.environ.copy()
    env["PORT"] = str(LOCAL_PORT)
    print(f"  PORT set to {LOCAL_PORT}")
    print(f"  Interpreter: {sys.executable}")
    print("  Press Ctrl+C to stop the app\n")
    cmd = [sys.executable, APP_ENTRYPOINT]
    try:
        subprocess.run(cmd, env=env, check=True)
        return True
    except KeyboardInterrupt:
        print("\n  Local run interrupted by user.")
        return True
    except subprocess.CalledProcessError as exc:
        print(f"  Local run exited with code {exc.returncode}")
        return False

# ============================================================================
# Cloud Deployments
# ============================================================================

def deploy_gcp():
    """Deploy to Google Cloud Run."""
    print("\n--- Deploying to GCP Cloud Run ---")
    if not check_tool("gcloud"):
        print("  Error: gcloud CLI not installed.")
        print("  Install: https://cloud.google.com/sdk/docs/install")
        return False

    cmd = (
        f"gcloud run deploy {SERVICE_NAME} "
        f"--image docker.io/{FULL_IMAGE_NAME} "
        f"--region {REGION_GCP} "
        f"--platform managed "
        f"--allow-unauthenticated "
        f"--port 8080"
    )
    return run_cmd(cmd)

def deploy_azure():
    """Deploy to Azure Container Apps."""
    print("\n--- Deploying to Azure Container Apps ---")
    if not check_tool("az"):
        print("  Error: Azure CLI (az) not installed.")
        print("  Install: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli")
        return False

    # az containerapp up is the simplest one-liner for deployment
    cmd = (
        f"az containerapp up "
        f"--name {SERVICE_NAME} "
        f"--image docker.io/{FULL_IMAGE_NAME} "
        f"--ingress external "
        f"--target-port 8080 "
        f"--location {REGION_AZURE}"
    )
    return run_cmd(cmd)

def deploy_aws():
    """Deploy to AWS App Runner."""
    print("\n--- Deploying to AWS App Runner ---")
    if not check_tool("aws"):
        print("  Error: AWS CLI not installed.")
        print("  Install: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html")
        return False

    print("  AWS App Runner requires more setup than a single command.")
    print("  Recommended: Use the AWS Console for first-time setup.")
    print(f"  1. Go to: https://console.aws.amazon.com/apprunner")
    print(f"  2. Create a new service from 'Container registry' -> 'Docker Hub'")
    print(f"  3. Use image: docker.io/{FULL_IMAGE_NAME}")
    print(f"  4. Set port to 8080")
    return True

# ============================================================================
# Main Menu
# ============================================================================

def main():
    print("=" * 50)
    print("Smart Confidant - Cloud Deployment")
    print("=" * 50)

    # Use pre-selected choice or prompt interactively
    if DEFAULT_CHOICE is not None:
        choice = str(DEFAULT_CHOICE)
        print(f"\nUsing DEFAULT_CHOICE={DEFAULT_CHOICE}")
    else:
        # Step 1: Build
        if not build_image():
            print("\nBuild failed. Exiting.")
            sys.exit(1)

        # Step 2: Push
        if not push_image():
            print("\nPush failed. Make sure you're logged in: docker login")
            sys.exit(1)

        print("\n" + "=" * 50)
        print("Image ready. Select deployment target:")
        print("=" * 50)
        print("  1. GCP Cloud Run")
        print("  2. Azure Container Apps")
        print("  3. AWS App Runner (manual)")
        print("  4. Skip deployment (image pushed to Docker Hub)")
        print("  5. Run locally (python app.py)")
        print()

        choice = input("Enter choice [1-5]: ").strip()

    if choice == "1":
        deploy_gcp()
    elif choice == "2":
        deploy_azure()
    elif choice == "3":
        deploy_aws()
    elif choice == "4":
        print("\nDone. Image available at:")
        print(f"  docker.io/{FULL_IMAGE_NAME}")
    elif choice == "5":
        run_local()
    else:
        print("Invalid choice.")
        sys.exit(1)

    print("\n" + "=" * 50)
    print("Deployment complete!")
    print("=" * 50)

if __name__ == "__main__":
    main()

