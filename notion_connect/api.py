import requests
import time
import asyncio
from tqdm import tqdm


class NotionClient:
    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }

    def post_comment(self, page_id: str, comment: str):
        resp = requests.post(
            url="https://api.notion.com/v1/comments",
            headers=self.headers,
            json={
                "parent": {"page_id": page_id},
                "rich_text": [{"text": {"content": comment}}],
            },
        )
        assert resp.status_code == 200, f"Failed to post comment: {resp.json()}"

    def get_pages(self, page_size: int = 100, sleep_time: int = 1):
        url = "https://api.notion.com/v1/search"
        payload = {"page_size": page_size}

        pages = []
        while True:
            response = requests.post(url=url, headers=self.headers, json=payload)
            data = response.json()
            for page in data["results"]:
                id = page["id"]
                title = page["properties"]["title"]["title"][0]["plain_text"]
                last_edited_time = page["last_edited_time"]
                created_time = page["created_time"]
                if page["in_trash"]:
                    continue
                pages.append(
                    {
                        "id": id,
                        "title": title,
                        "last_edited_time": last_edited_time,
                        "created_time": created_time,
                    }
                )

            if not data.get("has_more", False):
                break

            payload["start_cursor"] = data.get("next_cursor")

            time.sleep(sleep_time)

        return pages

    async def download_pages(
        self,
        page_ids: list[str],
        page_size: int = 100,
        sleep_time: int = 1,
        max_concurrent_requests: int = 3,
    ):
        sem = asyncio.Semaphore(max_concurrent_requests)
        results = []
        for page_id in tqdm(page_ids, desc="Downloading Pages"):
            results.append(await self.get_blocks(page_id, page_size, sleep_time, sem))
            time.sleep(sleep_time)
        return results

    async def get_blocks(
        self,
        page_id: str,
        page_size: int = 100,
        sleep_time: int = 1,
        sem: asyncio.Semaphore | None = asyncio.Semaphore(1),
    ):
        url = (
            f"https://api.notion.com/v1/blocks/{page_id}/children?page_size={page_size}"
        )

        next_cursor = None

        results = []
        while True:
            async with sem:
                response = requests.get(
                    url=f"{url}&start_cursor={next_cursor}" if next_cursor else url,
                    headers=self.headers,
                )
                data = response.json()
                results.extend(data["results"])
                next_cursor = data["next_cursor"]

                if not data.get("has_more", False):
                    break

                time.sleep(sleep_time)

        async def get_children(result):
            if not result["has_children"]:
                return result

            if result["type"] == "child_page":
                # Child Pages are going to trigger further recursive calls and they are already returned in get_pages()
                return result

            child = await self.get_blocks(result["id"])
            result["children"] = child
            return result

        coros = [get_children(result) for result in results]
        results = await asyncio.gather(*coros)

        return results
