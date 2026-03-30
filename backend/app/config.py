from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_verification_model: str = "gpt-4o-mini"
    openai_final_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    playwright_headless: bool = True
    playwright_timeout: int = 10000
    olta_base_url: str = "https://www.olta.re.kr"
    olta_max_results_per_query: int = 8
    olta_max_pages_per_collection: int = 16
    olta_max_detail_fetch: int = 96
    answer_context_top_k: int = 48
    verification_target_confidence: float = 0.8
    max_verification_rounds: int = 5

    gpki_cert_base_path: str = ""

    host: str = "127.0.0.1"
    port: int = 8000
    session_timeout_minutes: int = 30

    use_mock_crawler: bool = False
    use_mock_llm: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()


OLTA_SELECTORS = {
    "login": {
        "gpki_button": "button:has-text('GPKI 인증 로그인')",
        "cert_iframe": "iframe#certFrame",
        "storage_radio_hdd": "input[value='hdd']",
        "cert_list": ".cert-list .cert-item",
        "password_input": "input[type='password']#certPwd",
        "confirm_button": "button#confirmBtn",
        "logout_button": "a:has-text('로그아웃')",
    },
    "search": {
        "entry_url": "/main.do",
        "search_input": "input#query",
        "search_button": "a.search_icon",
        "result_title_links": "p.tt > a[onclick*='AddViewDocument']",
    },
}
