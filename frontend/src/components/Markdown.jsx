/**
 * A tiny, dependency-free Markdown renderer.
 *
 * The assistant answers in light Markdown (paragraphs, bullets, bold, inline
 * code) plus [S1]-style citation markers. Rather than pull in a full parser we
 * handle exactly that subset -- and, importantly, we build React elements
 * instead of setting innerHTML, so model output can never inject markup.
 */
import { Fragment } from 'react'

const INLINE = /(\*\*[^*]+\*\*|`[^`]+`|\[S\d+\])/g

function renderInline(text, onCitation) {
  return text.split(INLINE).map((part, index) => {
    if (!part) return null

    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={index}>{part.slice(2, -2)}</strong>
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={index}>{part.slice(1, -1)}</code>
    }
    // Citation marker -> a small clickable superscript.
    const citation = /^\[(S\d+)\]$/.exec(part)
    if (citation) {
      const ref = citation[1]
      return (
        <button
          key={index}
          onClick={() => onCitation?.(ref)}
          title={`Jump to source ${ref}`}
          className="mx-0.5 inline-flex h-[17px] min-w-[22px] items-center justify-center rounded border border-brand/30 bg-brand/10 px-1 align-super font-mono text-[10px] font-bold text-brand transition-colors hover:bg-brand/20"
        >
          {ref}
        </button>
      )
    }
    return <Fragment key={index}>{part}</Fragment>
  })
}

export function Markdown({ text, onCitation, className = 'prose-answer' }) {
  if (!text) return null

  const blocks = []
  let list = null
  let ordered = false

  const flush = () => {
    if (!list) return
    const Tag = ordered ? 'ol' : 'ul'
    blocks.push(
      <Tag key={`list-${blocks.length}`}>
        {list.map((item, index) => (
          <li key={index}>{renderInline(item, onCitation)}</li>
        ))}
      </Tag>
    )
    list = null
  }

  for (const rawLine of String(text).split('\n')) {
    const line = rawLine.trimEnd()

    if (!line.trim()) {
      flush()
      continue
    }

    const bullet = /^\s*[-*•]\s+(.*)$/.exec(line)
    const numbered = /^\s*\d+[.)]\s+(.*)$/.exec(line)

    if (bullet || numbered) {
      const isOrdered = Boolean(numbered)
      if (list && ordered !== isOrdered) flush()
      ordered = isOrdered
      list = list || []
      list.push((bullet || numbered)[1])
      continue
    }

    const heading = /^#{1,4}\s+(.*)$/.exec(line)
    if (heading) {
      flush()
      blocks.push(
        <p key={`h-${blocks.length}`} className="!mb-2 font-semibold text-ink">
          {renderInline(heading[1], onCitation)}
        </p>
      )
      continue
    }

    flush()
    blocks.push(<p key={`p-${blocks.length}`}>{renderInline(line, onCitation)}</p>)
  }
  flush()

  return <div className={className}>{blocks}</div>
}
