import json
import re
import urllib
from datetime import datetime
from os import path
from urlparse import urlparse


def Start():
    pass


VIXEN_SITES = {
    "vixen": "VIXEN",
    "tushy": "TUSHY",
    "tushyraw": "TUSHY RAW",
    "blacked": "BLACKED",
    "blackedraw": "BLACKED RAW",
    "deeper": "DEEPER",
    "milfy": "MILFY",
    "slayed": "SLAYED",
    "wifey": "WIFEY",
}
VIXEN_FILENAME_RE = re.compile(
    r"^.+? - (\d{4}-\d{2}-\d{2}) - (.+?)(?: \[(\d+)\])?\.mp4$", re.IGNORECASE
)
VIXEN_DEFAULT_DIR = "/Users/junz/.local/share/vixen"
vixen_cache = {}


def vixen_metadata_dir():
    return Prefs["vixen_metadata_dir"] or VIXEN_DEFAULT_DIR


def vixen_norm(name):
    return re.sub(r"[^a-z0-9]", "", name.lower(), flags=re.UNICODE)


def vixen_cast_set(cast_str):
    parts = re.split(r",\s*|\s+&\s+", cast_str)
    return frozenset(vixen_norm(p) for p in parts if p.strip())


def vixen_node_cast_set(node):
    return frozenset(vixen_norm(m["name"]) for m in (node.get("modelsSlugged") or []))


def vixen_load_site(site):
    file_path = path.join(vixen_metadata_dir(), site + ".json")
    mtime = path.getmtime(file_path)
    cached = vixen_cache.get(site)
    if cached and cached["mtime"] == mtime:
        return cached
    # stdlib json: JSON.ObjectFromString caps input at 5MB, site files exceed it
    edges = json.loads(Core.storage.load(file_path))
    by_date, by_video_id, by_slug = {}, {}, {}
    for edge in edges:
        node = edge["node"]
        by_date.setdefault(node["releaseDate"][:10], []).append(node)
        by_video_id[node["videoId"]] = node
        by_slug[node["slug"]] = node
    cached = {
        "mtime": mtime,
        "by_date": by_date,
        "by_video_id": by_video_id,
        "by_slug": by_slug,
    }
    vixen_cache[site] = cached
    return cached


def vixen_match(site, date_str, cast_str):
    idx = vixen_load_site(site)
    file_cast = vixen_cast_set(cast_str)
    candidates = idx["by_date"].get(date_str, [])
    if len(candidates) == 1:
        return candidates[0], 100
    if len(candidates) > 1:
        exact = [n for n in candidates if vixen_node_cast_set(n) == file_cast]
        if len(exact) == 1:
            return exact[0], 100
    if file_cast:
        target = datetime.strptime(date_str, "%Y-%m-%d")
        for d, nodes in idx["by_date"].items():
            if abs((datetime.strptime(d, "%Y-%m-%d") - target).days) <= 7:
                for n in nodes:
                    if vixen_node_cast_set(n) == file_cast:
                        return n, 90
    return None, 0


class LibreVixen(Agent.Movies):
    name = "LibreVixen"
    primary_provider = True
    languages = [
        Locale.Language.English,
        Locale.Language.NoLanguage,
    ]
    accepts_from = ["com.plexapp.agents.localmedia"]

    def search(self, results, media, lang, manual):
        try:
            Log("Manual: {}".format(manual))
            if manual and media.name and media.name.startswith("http"):
                self.searchByURL(results, media.name, lang)
                return

            filename = urllib.unquote(media.filename or "")
            if isinstance(filename, str):
                filename = filename.decode("utf-8")
            Log("File Name: {}".format(filename))
            folder = path.basename(path.dirname(filename)).lower()
            if folder.endswith(".com") and folder[:-4] in VIXEN_SITES:
                site = folder[:-4]
                m = VIXEN_FILENAME_RE.match(path.basename(filename))
                if m:
                    date_str, cast_str, video_id = m.groups()
                    node, score = None, 0
                    if video_id:
                        node = vixen_load_site(site)["by_video_id"].get(video_id)
                        score = 100
                    if node is None:
                        node, score = vixen_match(site, date_str, cast_str)
                    if node is not None:
                        Log("Matched: {} score {}".format(node["id"], score))
                        self.appendResult(results, site, node, score, lang)
                        return

            if manual and media.name:
                self.searchByTitle(results, media.name, lang)
        except Exception as e:
            Log.Exception("")

    def searchByURL(self, results, url, lang):
        parsed = urlparse(url)
        site = (parsed.hostname or "").replace("www.", "").replace(".com", "")
        slug = parsed.path.rstrip("/").split("/")[-1]
        if site in VIXEN_SITES:
            node = vixen_load_site(site)["by_slug"].get(slug)
            if node is not None:
                self.appendResult(results, site, node, 100, lang)

    def searchByTitle(self, results, query, lang):
        q = vixen_norm(query)
        if not q:
            return
        count = 0
        for site in VIXEN_SITES:
            try:
                by_video_id = vixen_load_site(site)["by_video_id"]
            except Exception:
                continue
            for node in by_video_id.values():
                if q in vixen_norm(node["title"]):
                    self.appendResult(results, site, node, 80, lang)
                    count += 1
                    if count >= 10:
                        return

    def appendResult(self, results, site, node, score, lang):
        results.Append(
            MetadataSearchResult(
                id="librevixen|{}|{}".format(site, node["videoId"]),
                name="{} - {}".format(VIXEN_SITES[site], node["title"]),
                year=int(node["releaseDate"][:4]),
                score=score,
                lang=lang,
            )
        )

    def update(self, metadata, media, lang):
        try:
            if not metadata.id.startswith("librevixen|"):
                return
            Log.Info("ID: {}".format(metadata.id))
            prefix, site, video_id = metadata.id.split("|", 2)
            node = vixen_load_site(site)["by_video_id"].get(video_id)
            if node is None:
                Log.Error("No metadata entry for {}".format(metadata.id))
                return

            # Title
            metadata.title = "{} - {}".format(VIXEN_SITES[site], node["title"])

            # Originally Available At / Year
            date = datetime.strptime(node["releaseDate"][:10], "%Y-%m-%d")
            metadata.originally_available_at = date
            metadata.year = date.year

            # Studio
            metadata.studio = VIXEN_SITES[site]

            # Collections
            metadata.collections.clear()
            metadata.collections.add(VIXEN_SITES[site])

            # Roles
            metadata.roles.clear()
            for model in node.get("modelsSlugged") or []:
                metadata.roles.new().name = model["name"]

            # Posters / Art
            listing = ((node.get("images") or {}).get("listing")) or []
            portraits = [i for i in listing if i["height"] > i["width"]]
            landscapes = [i for i in listing if i["width"] >= i["height"]]
            if portraits:
                url = (portraits[0].get("highdpi") or {}).get("double") or portraits[0][
                    "src"
                ]
                metadata.posters[url] = Proxy.Preview(HTTP.Request(url))
            if landscapes:
                best = max(landscapes, key=lambda i: i["width"])
                url = (best.get("highdpi") or {}).get("double") or best["src"]
                metadata.art[url] = Proxy.Preview(HTTP.Request(url))
        except Exception as e:
            Log.Exception("")
