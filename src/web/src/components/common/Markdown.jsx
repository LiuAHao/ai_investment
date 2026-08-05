import React from 'react'

/**
 * 轻量 Markdown 渲染器（无外部依赖）
 * 支持：标题 #/##/###、粗体 **、斜体 *、无序列表 -、有序列表 1.、
 * 行内代码 `code`、引用 >、分隔线 ---、链接 [text](url)、多行段落
 */

function inline(text) {
  if (!text) return ''
  let html = String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  // 行内代码（先处理，避免破坏其他语法）
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
  // 链接
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
  // 粗体
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  // 斜体
  html = html.replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
  return html
}

function parseMarkdown(text) {
  if (!text) return []
  const lines = String(text).split('\n')
  const blocks = []
  let list = null
  let listType = ''
  let quote = null
  let para = ''

  const flushList = () => {
    if (list) {
      blocks.push({ type: 'list', ordered: listType === 'ol', items: list })
      list = null
      listType = ''
    }
  }
  const flushQuote = () => {
    if (quote !== null) {
      blocks.push({ type: 'quote', text: quote })
      quote = null
    }
  }
  const flushPara = () => {
    if (para.trim()) {
      blocks.push({ type: 'p', text: para.trim() })
      para = ''
    }
  }

  for (const raw of lines) {
    const line = raw.trim()

    // 分隔线
    if (/^(-{3,}|\*{3,})$/.test(line)) {
      flushList(); flushQuote(); flushPara()
      blocks.push({ type: 'hr' })
      continue
    }

    // 引用
    if (/^>\s?/.test(line)) {
      flushList(); flushPara()
      if (quote === null) quote = ''
      quote += (quote ? '\n' : '') + line.replace(/^>\s?/, '')
      continue
    }

    // 标题
    const heading = line.match(/^(#{1,4})\s+(.*)/)
    if (heading) {
      flushList(); flushQuote(); flushPara()
      blocks.push({ type: 'heading', level: heading[1].length, text: inline(heading[2]) })
      continue
    }

    // 无序列表
    const ul = line.match(/^[-*•]\s+(.*)/)
    // 有序列表
    const ol = line.match(/^\d+[.、]\s+(.*)/)
    if (ul || ol) {
      flushQuote(); flushPara()
      if (!list) { list = []; listType = ol ? 'ol' : 'ul' }
      list.push(inline((ul ? ul[1] : ol[1]) || ''))
      continue
    }

    // 空行：结束当前块
    if (!line) {
      flushList(); flushQuote(); flushPara()
      continue
    }

    // 普通段落
    flushList(); flushQuote()
    para += (para ? '\n' : '') + inline(line)
  }

  flushList(); flushQuote(); flushPara()
  return blocks
}

const Markdown = ({ text, className = '' }) => {
  const blocks = parseMarkdown(text)
  return (
    <div className={`md-render ${className}`}>
      {blocks.map((block, i) => {
        switch (block.type) {
          case 'heading':
            return block.level === 1
              ? <h3 key={i} dangerouslySetInnerHTML={{ __html: block.text }} />
              : <h4 key={i} dangerouslySetInnerHTML={{ __html: block.text }} />
          case 'p':
            return <p key={i} dangerouslySetInnerHTML={{ __html: block.text }} />
          case 'list':
            return block.ordered ? (
              <ol key={i}>{block.items.map((it, j) => <li key={j} dangerouslySetInnerHTML={{ __html: it }} />)}</ol>
            ) : (
              <ul key={i}>{block.items.map((it, j) => <li key={j} dangerouslySetInnerHTML={{ __html: it }} />)}</ul>
            )
          case 'quote':
            return <blockquote key={i} dangerouslySetInnerHTML={{ __html: inline(block.text) }} />
          case 'hr':
            return <hr key={i} />
          default:
            return null
        }
      })}
    </div>
  )
}

export default Markdown
