import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type

from utils import pick_user_agent, DomainRateLimiter, normalize_url

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# rate limiter global (por processo)
_rate = DomainRateLimiter(min_interval=1.2, jitter=0.4)

TRANSIENT = (
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
)

@retry(
    reraise=True,
    stop=stop_after_attempt(4),
    wait=wait_exponential_jitter(initial=1, max=20),
    retry=retry_if_exception_type(TRANSIENT),
)
def _http_get(url: str, timeout: int = 25) -> requests.Response:
    _rate.wait(url)
    headers = {
        "User-Agent": pick_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    }
    return requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)

def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    # remove scripts/styles
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    return text

def _try_jina(url: str) -> str | None:
    """
    Fallback gratuito: r.jina.ai (boa chance de extrair texto limpo).
    """
    jina_url = "https://r.jina.ai/http://" + normalize_url(url).replace("https://", "").replace("http://", "")
    try:
        _rate.wait(jina_url)
        headers = {"User-Agent": pick_user_agent()}
        r = requests.get(jina_url, headers=headers, timeout=25)
        if r.status_code == 200 and len(r.text) > 400:
            return r.text
        return None
    except Exception:
        return None

def get_page_text(url: str) -> str:
    """
    Scraper robusto:
    1) tenta jina
    2) fallback requests + bs4
    Levanta exceção em status claramente inválidos.
    """
    url = normalize_url(url)

    # 1) tenta jina
    jina = _try_jina(url)
    if jina:
        return jina

    # 2) requests normal
    resp = _http_get(url)

    # status handling
    if resp.status_code in (404, 410):
        raise RuntimeError(f"Page removed ({resp.status_code})")
    if resp.status_code in (401, 403):
        # pode ser bloqueio; ainda dá para tentar parsear, mas marque como duvidosa depois
        # aqui devolvemos texto, mas curto
        return f"HTTP {resp.status_code} - possível bloqueio ao acessar: {url}\n\n" + (resp.text[:2000] if resp.text else "")

    resp.raise_for_status()

    text = _html_to_text(resp.text)
    if len(text) < 200:
        raise RuntimeError("Texto muito curto após parse HTML")
    return text



def fetch_text_with_jina(url: str, timeout: int = 25) -> str:
    """
    Tenta usar o reader gratuito do Jina:
    https://r.jina.ai/http(s)://...
    Retorna texto/markdown.
    """
    jina_url = "https://r.jina.ai/" + url
    r = requests.get(jina_url, headers=DEFAULT_HEADERS, timeout=timeout)
    r.raise_for_status()
    text = r.text.strip()
    return text


def fetch_text_with_requests(url: str, timeout: int = 25) -> str:
    """
    Fallback: baixa HTML e extrai texto bruto.
    """
    r = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")

    # remove scripts e styles
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)


# def get_page_text(url: str) -> str:
#     """
#     Estratégia MVP:
#     1) tenta Jina
#     2) fallback requests+bs4
#     """
#     try:
#         return fetch_text_with_jina(url)
#     except Exception:
#         return fetch_text_with_requests(url)
