import os
from huggingface_hub import upload_file

if __name__ == "__main__":
    hf_token = os.environ.get("HF_TOKEN")

    if hf_token:
        print(f"Token found! Token length: {len(hf_token)}")
    else:
        print("No token found")

    upload_file(path_or_fileobj="openaip.pmtiles", 
                path_in_repo="openaip.pmtiles",
                repo_id="jobes666/openaip-mptiles", 
                repo_type="dataset", 
                token=hf_token)