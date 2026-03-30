import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default function StreamingResponse({ content }) {
  return (
    <div className="prose prose-sm max-w-none prose-headings:mb-3 prose-headings:mt-0 prose-p:my-2 prose-table:text-sm">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  )
}
