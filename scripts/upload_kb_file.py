"""Upload a single KB file to the Foundry vector store.

Uses DeviceCodeCredential and the project endpoint from .env.
The file is uploaded to Foundry file storage and then added to
the existing vector store identified by VECTOR_STORE_ID.

Usage:
    python scripts/upload_kb_file.py kb/about/01-about-telsano.md
"""

import sys
from pathlib import Path

from azure.ai.agents import AgentsClient
from azure.ai.agents.models import FilePurpose
from azure.identity import DeviceCodeCredential

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_config


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/upload_kb_file.py <path-to-file>")
        sys.exit(1)

    file_path = Path(sys.argv[1])
    if not file_path.is_absolute():
        file_path = PROJECT_ROOT / file_path
    if not file_path.exists():
        print(f"File not found: {file_path}")
        sys.exit(1)

    cfg = get_config()

    print("Authenticating via Device Code...")
    credential = DeviceCodeCredential(tenant_id=cfg.AZURE_TENANT_ID)
    client = AgentsClient(endpoint=cfg.AZURE_FOUNDRY_PROJECT_ENDPOINT, credential=credential)

    print(f"Uploading {file_path.name} ...")
    uploaded = client.files.upload_and_poll(
        file_path=str(file_path),
        purpose=FilePurpose.AGENTS,
    )
    print(f"File uploaded: {uploaded.id}")

    print(f"Adding to vector store {cfg.VECTOR_STORE_ID} ...")
    vf = client.vector_stores.files.create_and_poll(
        vector_store_id=cfg.VECTOR_STORE_ID,
        file_id=uploaded.id,
    )
    print(f"Done. {file_path.name} is indexed in the vector store (status: {vf.status}).")


if __name__ == "__main__":
    main()
