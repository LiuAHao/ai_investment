import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const SAFE_LINK = /^(https?:\/\/|mailto:|#|\/)/i

/**
 * Markdown 渲染器
 * 使用 react-markdown + GFM，支持表格、代码块、嵌套列表。
 * 默认转义 HTML，并拦截 javascript: 等不安全链接。
 */
const Markdown = ({ text, className = '' }) => {
  if (!text) return null

  return (
    <div className={`md-render ${className}`.trim()}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a({ href, title, children }) {
            if (!href || !SAFE_LINK.test(href)) {
              return <span title={title}>{children}</span>
            }
            const external = /^https?:\/\//i.test(href)
            return (
              <a
                href={href}
                title={title}
                {...(external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
              >
                {children}
              </a>
            )
          },
          table({ children }) {
            return <div className="md-table-wrap"><table>{children}</table></div>
          },
        }}
      >
        {String(text)}
      </ReactMarkdown>
    </div>
  )
}

export default Markdown
