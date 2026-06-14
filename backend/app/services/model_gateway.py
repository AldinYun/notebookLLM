import json
from collections.abc import Iterator
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ModelGatewayError(RuntimeError):
    pass


class ModelGateway:
    def list_models(self, connection: dict, api_key: str = "") -> list[str]:
        payload = self._request_json(
            method="GET",
            url=f"{connection['base_url'].rstrip('/')}/models",
            api_key=api_key,
        )
        return [str(model.get("id")) for model in payload.get("data", []) if model.get("id")]

    def generate(
        self,
        connection: dict,
        question: str,
        citations: list[dict],
        api_key: str = "",
    ) -> str:
        evidence = "\n\n".join(
            f"[{citation['citation_id']}] {citation['document_title']} "
            f"(page {citation['page_start']}): {citation['quote']}"
            for citation in citations
        )
        payload = self._request_json(
            method="POST",
            url=f"{connection['base_url'].rstrip('/')}/chat/completions",
            api_key=api_key,
            body={
                "model": connection["model_id"],
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Answer only from the supplied evidence. Cite evidence using [C1], [C2], "
                            "and say when evidence is insufficient."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Question: {question}\n\nEvidence:\n{evidence}",
                    },
                ],
                "temperature": 0.1,
                "stream": False,
            },
        )
        try:
            return str(payload["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as error:
            raise ModelGatewayError("Model response did not contain choices[0].message.content") from error

    def stream_generate(
        self,
        connection: dict,
        question: str,
        citations: list[dict],
        api_key: str = "",
    ) -> Iterator[str]:
        evidence = "\n\n".join(
            f"[{citation['citation_id']}] {citation['document_title']} "
            f"(page {citation['page_start']}): {citation['quote']}"
            for citation in citations
        )
        headers = {"Accept": "text/event-stream", "Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        body = json.dumps(
            {
                "model": connection["model_id"],
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Answer only from the supplied evidence. Cite evidence using [C1], [C2], "
                            "and say when evidence is insufficient."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Question: {question}\n\nEvidence:\n{evidence}",
                    },
                ],
                "temperature": 0.1,
                "stream": True,
            }
        ).encode("utf-8")
        request = Request(
            url=f"{connection['base_url'].rstrip('/')}/chat/completions",
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=60) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    payload = json.loads(data)
                    content = payload.get("choices", [{}])[0].get("delta", {}).get("content")
                    if content:
                        yield str(content)
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise ModelGatewayError(f"Model endpoint returned HTTP {error.code}: {detail}") from error
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            raise ModelGatewayError(f"Model streaming request failed: {error}") from error

    def _request_json(
        self,
        method: str,
        url: str,
        api_key: str,
        body: dict | None = None,
    ) -> dict:
        headers = {"Accept": "application/json"}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        request = Request(url=url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise ModelGatewayError(f"Model endpoint returned HTTP {error.code}: {detail}") from error
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            raise ModelGatewayError(f"Model endpoint request failed: {error}") from error


model_gateway = ModelGateway()
