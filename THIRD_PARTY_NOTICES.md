# Third-party dependencies

Checked on 2026-11-02 against the installed distributions. This repository contains the application source, not bundled Python packages or model weights. Dependencies retain their own licenses; this document does not replace their full notices or grant additional rights.

## YomiToku and model weights

- Project: [YomiToku](https://github.com/kotaro-kinoshita/yomitoku)
- Attribution: YomiToku © 2024 by Kotaro Kinoshita.
- Installed package: `yomitoku==0.15.1`.
- License: [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).
- Recognition model: [parseq-middle-dynw-v5](https://huggingface.co/KotaroKinoshita/yomitoku-text-recognizer-parseq-middle-dynw-v5).
- Detection model: [dbnet-v2_1](https://huggingface.co/KotaroKinoshita/yomitoku-text-detector-dbnet-v2_1).

The installed YomiToku 0.15.1 package description expressly applies CC BY-NC-SA 4.0 to its source code and associated Hugging Face model weights. The individual model cards do not themselves state a license; the package's project-wide declaration is the basis for the model attribution here.

The application calls YomiToku through its Python API. It does not redistribute its implementation or weights. Models are downloaded by each user and stored in the ignored `data/models/` directory. Configuration files select the original models; no model training or weight modification is performed.

Noncommercial personal use is expressly permitted by the package description. See the author's [commercial-use guideline](https://kotaro-kinoshita.github.io/yomitoku/en/commercial_use_guideline/) for business deployments and other uses. An application-source license does not remove restrictions on its dependencies. Distribution of adaptations of CC-licensed material requires attribution, identification of changes, and compliance with ShareAlike. Do not assume that merely importing a dependency automatically determines the license of all independently written application code.

## Direct dependencies

License identifiers below come from the installed package metadata.

| Package | Version checked | License |
| --- | --- | --- |
| streamlit | 1.66.1 | Apache-2.0 |
| Pillow | 12.3.0 | MIT-CMU |
| google-api-python-client | 2.201.0 | Apache-2.0 |
| google-auth-oauthlib | 1.5.0 | Apache-2.0 |
| python-dotenv | 1.2.4 | BSD-3-Clause |
| pydantic | 2.14.2 | MIT |
| numpy | 2.4.6 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| streamlit-paste-button | 0.1.2 | MIT |
| opencv-python | 5.0.0.93 | Apache-2.0 |
| yomitoku | 0.15.1 | CC BY-NC-SA 4.0 |


## Scope of review

This is a source-only release check, not a complete audit of all transitive dependencies or upstream code provenance. `requirements.lock.txt` records the installed environment; each dependency supplies its own applicable notices. Packaging a virtual environment, executable, container, or model bundle requires a separate redistribution review, including all transitive components and bundled native libraries.
