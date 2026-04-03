from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_verification_model: str = "gpt-4o-mini"
    openai_final_model: str = "gpt-4o"
    openai_summarization_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    playwright_headless: bool = False
    playwright_timeout: int = 10000
    olta_base_url: str = "https://www.olta.re.kr"
    olta_max_results_per_query: int = 8
    olta_max_pages_per_collection: int | None = 3
    olta_max_detail_fetch: int = 20
    olta_bbs_max_pages_per_board: int = 2
    olta_bbs_concurrency: int = 3
    olta_bbs_enabled: bool = True
    olta_bbs_debug: bool = False
    olta_bbs_mode: str = "discovery"
    olta_bbs_dump_dir: str = "debug/bbs"
    olta_bbs_popup_wait_timeout_ms: int = 2500
    olta_bbs_same_tab_wait_timeout_ms: int = 2500
    olta_bbs_detail_ready_timeout_ms: int = 3000
    olta_bbs_restore_timeout_ms: int = 5000
    olta_shared_user_data_dir: str = "backend/.playwright/olta-shared-profile"
    answer_context_top_k: int = 40
    verification_target_confidence: float = 0.8
    max_verification_rounds: int = 5
    crawler_content_limit: int | None = None

    gpki_cert_base_path: str = ""

    host: str = "127.0.0.1"
    port: int = 8000
    session_timeout_minutes: int = 30

    search_max_keywords: int = 10
    search_use_llm_extraction: bool = True

    ranking_semantic_weight: float = 0.6
    ranking_overlap_weight: float = 0.2
    ranking_position_weight: float = 0.1
    ranking_year_weight: float = 0.1
    ranking_diversity_divisor: int = 6
    embedding_content_limit: int = 1500

    grouping_similarity_high: float = 0.84
    grouping_similarity_medium: float = 0.76
    grouping_title_overlap_with_medium: float = 0.35
    grouping_title_overlap_standalone: float = 0.55
    grouping_content_limit: int = 1200
    grouping_review_content_limit: int = 600

    summary_content_limit: int = 900
    summary_max_tokens: int = 900
    max_representative_sources: int = 4

    draft_max_tokens: int = 1800
    draft_temperature: float = 0.2
    revision_max_tokens: int = 1800
    revision_temperature: float = 0.1
    final_max_tokens: int = 1800

    aggregator_penalty_not_found: float = 0.3
    aggregator_penalty_mismatch: float = 0.5
    aggregator_penalty_expired: float = 0.4
    aggregator_penalty_no_citation: float = 0.2
    aggregator_slot_contradicted: float = 0.2
    aggregator_slot_unused: float = 0.5
    aggregator_slot_partial: float = 0.8
    aggregator_claim_weight: float = 0.55
    aggregator_source_weight: float = 0.25
    aggregator_slot_weight: float = 0.2
    aggregator_cap_hallucinated: float = 0.34
    aggregator_cap_unsupported_heavy: float = 0.45
    aggregator_cap_source_failure: float = 0.4
    aggregator_cap_slot_gap: float = 0.6
    aggregator_cap_low_citation_coverage: float = 0.55
    aggregator_cap_low_verified_citation_ratio: float = 0.65
    aggregator_cap_low_supported_ratio: float = 0.6

    confidence_very_high: float = 0.85
    confidence_high: float = 0.7
    confidence_medium: float = 0.4

    stagnation_threshold: float = 0.02
    low_confidence_warning: float = 0.5

    cv_confidence_supported: float = 0.85
    cv_confidence_partial: float = 0.5
    cv_confidence_unsupported: float = 0.2
    cv_confidence_strong_supported: float = 0.9
    cv_confidence_no_source_assertive: float = 0.05

    slot_fallback_supported: float = 0.85
    slot_fallback_partial: float = 0.55
    slot_fallback_unused: float = 0.2

    web_search_max_results: int = 5
    max_research_iterations: int = 1
    research_confidence_threshold: float = 0.75

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


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
        "sub_board": {
            "tab_container_selectors": [
                ".tab_area",
                ".sub_tab",
                ".category_tab",
                ".search_tab",
                ".result_tab",
                "[class*='tab']",
                ".tax_type",
                ".sub_menu",
                ".depth2",
            ],
            "tab_link_selectors": [
                "a[onclick*='doTaxType']",
                "a[onclick*='doSubCollection']",
                "a[onclick]",
                "button[onclick]",
                "li[onclick]",
                "li a",
                "a",
                "button",
            ],
            "count_selectors": [
                ".count",
                ".num",
                ".total",
                ".badge",
                "span",
                "em",
            ],
            "known_labels": [
                "취득",
                "등록면허",
                "주민",
                "지방소득",
                "재산",
                "자동차",
                "기타",
            ],
        },
    },
    "bbs": {
        "entry_url": "/search/PU_0003_search.jsp",
        "search_input": "input#queryPu",
        "search_button_js": "doSearchPu()",
        "result_container_selectors": [
            ".search_list",
            ".result_list",
            ".board_list",
            ".contents",
            "#content",
            "body",
        ],
        "board_trigger_selectors": [
            "select[name*='brd']",
            "select[id*='brd']",
            "select[name*='board']",
            "select[id*='board']",
            "input[type='radio'][name*='brd']",
            "input[type='radio'][name*='board']",
            "[onclick*='doBrdNmCollection']",
        ],
        "result_link_selectors": [
            "a[onclick*='bbsPopUp']",
            "a[onclick*='Bbs']",
            "a[href*='bbsId=']",
            "a[href*='nttId=']",
            "p.tt > a[onclick]",
            "li a[onclick]",
        ],
        "result_title_link_selectors": [
            "p.tt > a",
            "dt a",
            "td a",
            "li a",
            "a[onclick]",
            "a[href]",
        ],
        "result_row_selectors": [
            "ul li",
            "ol li",
            ".search_list li",
            ".result_list li",
            ".board_list li",
            "table tbody tr",
        ],
        "empty_state_selectors": [
            ".no_data",
            ".empty",
            ".nodata",
        ],
        "detail_content_selectors": [
            ".board_view",
            ".view_cont",
            ".detail_cont",
            ".bbs_view",
            ".contents",
            "#content",
            "body",
        ],
        "detail_ready_selectors": [
            ".board_view",
            ".view_cont",
            ".detail_cont",
            ".bbs_view",
            ".board_detail",
            ".board_cont",
            ".contents",
            "#content",
        ],
        "modal_selectors": [
            ".modal.show",
            ".popup.show",
            ".layer_popup",
            ".ui-dialog",
        ],
        "iframe_selectors": [
            "iframe[name*='bbs']",
            "iframe[id*='bbs']",
            "iframe[src*='bbsId=']",
            "iframe[src*='nttId=']",
        ],
        "page_ready_selectors": [
            "input#queryPu",
            ".search_list",
            ".result_list",
            ".board_list",
        ],
    },
}
