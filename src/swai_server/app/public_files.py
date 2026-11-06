# Copyright (C) 2024 Josua Krause
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Serves the public files of the client whose content depends on the
deployment. The files in `src/swai_client/public/` contain placeholders of the
form `@@NAME@@` which are filled in from the server's environment when the
file is requested.
"""
import os
from http.cookies import SimpleCookie
from urllib.parse import urlsplit

from quick_server import PreventDefaultResponse, QuickServer
from quick_server import QuickServerRequestHandler as QSRH
from quick_server import ReqArgs, Response


def fill_template(content: str, values: dict[str, str]) -> str:
    """
    Replaces every `@@NAME@@` placeholder with its value.

    Args:
        content (str): The template.
        values (dict[str, str]): The values by placeholder name.

    Returns:
        str: The filled in template.
    """
    for key, value in values.items():
        content = content.replace(f"@@{key}@@", value)
    return content


def setup_public_files(
        server: QuickServer,
        *,
        public_path: str,
        public_url: str,
        provider_registry: str,
        model_url: str) -> None:
    """
    Registers the handlers for the deployment specific public files. They
    take precedence over the static files of the client.

    Args:
        server (QuickServer): The server.
        public_path (str): The folder of the built client.
        public_url (str): The public URL of the server without trailing
            slash (OWN_URL). If it is empty no sitemap is served.
        provider_registry (str): The image prefix of the provider images
            (PROVIDER_REGISTRY).
        model_url (str): The download URL of the model for the worker script
            (MODEL_URL).
    """
    values = {
        "PUBLIC_URL": public_url,
        "PROVIDER_REGISTRY": provider_registry,
        "MODEL_URL": model_url,
    }

    def read_file(fname: str) -> str:
        path = os.path.join(public_path, fname)
        if not os.path.isfile(path):
            raise PreventDefaultResponse(404, "File not found")
        with open(path, "r", encoding="utf-8") as fin:
            return fin.read()

    @server.text_get("/robots.txt")
    def _get_robots(_req: QSRH, _rargs: ReqArgs) -> Response:
        content = read_file("robots.txt")
        if not public_url:
            # a sitemap reference must be an absolute URL
            content = "".join(
                line
                for line in content.splitlines(keepends=True)
                if not line.startswith("Sitemap:"))
        return Response(fill_template(content, values), 200, "text/plain")

    @server.text_get("/sitemap.xml")
    def _get_sitemap(_req: QSRH, _rargs: ReqArgs) -> Response:
        if not public_url:
            raise PreventDefaultResponse(404, "File not found")
        content = read_file("sitemap.xml")
        return Response(
            fill_template(content, values), 200, "application/xml")

    @server.text_get("/scripts/run-worker.sh")
    def _get_run_worker(_req: QSRH, _rargs: ReqArgs) -> Response:
        content = read_file("scripts/run-worker.sh")
        return Response(
            fill_template(content, values), 200, "application/x-sh")


def setup_www_redirect(server: QuickServer, public_url: str) -> None:
    """
    Redirects requests for the bare domain to the public URL if the public
    URL is on the www subdomain.

    Args:
        server (QuickServer): The server.
        public_url (str): The public URL of the server without trailing
            slash (OWN_URL).
    """
    public_host = urlsplit(public_url).netloc
    if not public_host.startswith("www."):
        return
    bare_host = public_host.removeprefix("www.")

    def redirect_to_www(
            req: QSRH, path: str, _cookie: SimpleCookie | None) -> None:
        _proto, orig_host = req.get_original_host()
        if orig_host.removesuffix("/") != bare_host:
            return
        req.send_header("Location", f"{public_url}{path}")
        raise PreventDefaultResponse(301, "Use www subdomain.")

    server.add_pre_middleware(redirect_to_www)
