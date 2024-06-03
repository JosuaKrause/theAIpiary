### Add your own GPU to the swarm.

On Linux (or WSL), install [Docker](https://docs.docker.com/engine/install/) and
[CUDA](https://docs.nvidia.com/cuda/cuda-installation-guide-linux/). On WSL you
will have to perform additional steps to make both available to the WSL
subsystem. After that, download the [run-worker.sh](/scripts/run-worker.sh),
move it to the folder of your choice, and make it executable:
`chmod +x run-worker.sh`. You can run it now via `./run-worker.sh`.
The script will prompt you for your user name (your email address) and your
worker token (obtain below). The script will also attempt to download the
Llama 3 model. If this fails you can download the
[model directly](https://huggingface.co/bartowski/Meta-Llama-3-8B-Instruct-GGUF/resolve/main/Meta-Llama-3-8B-Instruct-Q6_K.gguf?download=true) and move it to the location indicated by the script.
Once everything works you will be able to see your worker bee in the worker list
above.
