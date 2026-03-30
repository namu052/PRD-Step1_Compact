export default function TopBar() {
  return (
    <header className="bg-slate-800 text-white px-6 py-3 flex items-center justify-between shrink-0">
      <h1 className="text-lg font-semibold tracking-tight">
        🏛️ AI 지방세 지식인
      </h1>
      <div className="flex items-center gap-4">
        <span className="text-sm text-slate-300">OLTA 페이지를 함께 엽니다</span>
        <a
          href="https://www.olta.re.kr"
          target="_blank"
          rel="noreferrer"
          className="text-sm px-3 py-1 rounded bg-slate-700 hover:bg-slate-600 transition"
        >
          OLTA 열기
        </a>
      </div>
    </header>
  )
}
