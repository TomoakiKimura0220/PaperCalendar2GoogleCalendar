#!/bin/zsh
set -e
cd "${0:A:h}"
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
if ! .venv/bin/python -c "import streamlit, PIL, googleapiclient, google_auth_oauthlib, dotenv, streamlit_paste_button, cv2, yomitoku" 2>/dev/null; then
  .venv/bin/python -m pip install -r requirements.txt
fi
exec .venv/bin/python -m streamlit run app.py --server.address 127.0.0.1
