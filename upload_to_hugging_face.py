import os
from huggingface_hub import upload_file
hf_token = os.environ.get("HF_TOKEN")
upload_file(path_or_fileobj="openaip.pmtiles", 
            path_in_repo="openaip.pmtiles",
            repo_id="jobes666/openaip-mptiles", 
            repo_type="dataset", 
            token=hf_token)