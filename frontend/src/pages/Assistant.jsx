import { useCallback, useEffect, useRef, useState } from 'react'
import { useApp } from '../context/AppContext'
import * as api from '../services/api'
import { Markdown } from '../components/Markdown'
import { PageHeader } from '../components/PageState'
import { RetrievalTrace, SourceList } from '../components/Sources'
import { Button, Card, EmptyState, Modal, Spinner, cx } from '../components/ui'
import { useNavigate } from 'react-router-dom'

export default function Assistant() {
  const navigate = useNavigate()
  const { sessionId, ready, toastError } = useApp()

  const [messages, setMessages] = useState([])
  const [suggested, setSuggested] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [openSource, setOpenSource] = useState(null)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    if (!sessionId) return
    api
      .getChatHistory(sessionId)
      .then((data) => {
        setMessages(data.messages || [])
        setSuggested(data.suggested || [])
      })
      .catch(() => {})
  }, [sessionId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, sending])

  const send = useCallback(
    async (question) => {
      const text = (question ?? input).trim()
      if (!text || sending) return

      setInput('')
      setMessages((current) => [...current, { role: 'user', content: text, sources: [] }])
      setSending(true)

      try {
        const answer = await api.askQuestion(sessionId, text)
        setMessages((current) => [
          ...current,
          {
            role: 'assistant',
            content: answer.answer,
            sources: answer.sources,
            found_answer: answer.found_answer,
            follow_ups: answer.follow_ups,
            retrieval: answer.retrieval,
          },
        ])
      } catch (error) {
        toastError(error)
        setMessages((current) => [
          ...current,
          {
            role: 'assistant',
            content: `**${error.message}**${error.hint ? `\n\n${error.hint}` : ''}`,
            sources: [],
            isError: true,
          },
        ])
      } finally {
        setSending(false)
        inputRef.current?.focus()
      }
    },
    [input, sending, sessionId, toastError]
  )

  const clear = async () => {
    try {
      await api.clearChat(sessionId)
      setMessages([])
    } catch (error) {
      toastError(error)
    }
  }

  if (!ready) {
    return (
      <EmptyState
        icon={<span aria-hidden="true">💬</span>}
        title="The assistant needs both documents"
        description="It answers by retrieving passages from your resume and the job description, so it needs both before it can say anything useful."
        action={<Button onClick={() => navigate('/upload')}>Go to documents</Button>}
      />
    )
  }

  return (
    <div className="mx-auto flex h-[calc(100vh-8.5rem)] max-w-4xl flex-col">
      <PageHeader
        title="AI Assistant"
        subtitle="Every answer is retrieved from your documents first, then written — with a citation you can open."
        action={
          messages.length > 0 && (
            <Button size="sm" variant="ghost" onClick={clear}>
              Clear chat
            </Button>
          )
        }
      />

      {/* ---------------------------------------------------- transcript */}
      <div className="mt-5 min-h-0 flex-1 space-y-5 overflow-y-auto pr-1">
        {messages.length === 0 && (
          <Card className="card-pad">
            <p className="text-[14px] font-semibold text-ink">Ask me about your match</p>
            <p className="mt-1.5 text-[13px] leading-relaxed text-muted">
              I can only see what's in your resume and this job description. If something isn't in
              them, I'll say so rather than guess.
            </p>
            <div className="mt-4 grid gap-2 sm:grid-cols-2">
              {suggested.map((question) => (
                <button
                  key={question}
                  onClick={() => send(question)}
                  className="rounded-xl border border-line px-3.5 py-2.5 text-left text-[13px] text-muted transition-all hover:border-brand/50 hover:bg-raised/60 hover:text-ink"
                >
                  {question}
                </button>
              ))}
            </div>
          </Card>
        )}

        {messages.map((message, index) => (
          <Message
            key={index}
            message={message}
            onCitation={(ref) => {
              const position = Number(String(ref).replace('S', '')) - 1
              const source = message.sources?.[position]
              if (source) setOpenSource(source)
            }}
            onFollowUp={send}
          />
        ))}

        {sending && (
          <div className="flex items-center gap-2.5 text-[13px] text-muted">
            <Spinner className="h-3.5 w-3.5" />
            Searching your documents, then answering...
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* -------------------------------------------------------- composer */}
      <form
        onSubmit={(event) => {
          event.preventDefault()
          send()
        }}
        className="mt-4 shrink-0"
      >
        <div className="flex items-end gap-2 rounded-2xl border border-line bg-surface p-2 shadow-card focus-within:border-brand/50">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                send()
              }
            }}
            rows={1}
            placeholder="Ask about your skills, projects, gaps, or what this job requires..."
            className="max-h-32 min-h-[38px] flex-1 resize-none bg-transparent px-2.5 py-2 text-[14px] leading-relaxed text-ink placeholder:text-subtle focus:outline-none"
          />
          <Button type="submit" size="md" disabled={!input.trim() || sending} className="shrink-0">
            <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 10h13M11 5l5 5-5 5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span className="hidden sm:inline">Ask</span>
          </Button>
        </div>
        <p className="mt-2 text-center text-[11.5px] text-subtle">
          Enter to send · Shift+Enter for a new line
        </p>
      </form>

      <Modal
        open={Boolean(openSource)}
        onClose={() => setOpenSource(null)}
        title={openSource?.citation || 'Source'}
        subtitle={openSource ? `Similarity ${(openSource.score * 100).toFixed(0)}%` : ''}
      >
        {openSource && (
          <pre className="whitespace-pre-wrap rounded-xl border border-line bg-raised/60 p-4 font-sans text-[13.5px] leading-relaxed text-ink">
            {openSource.text}
          </pre>
        )}
      </Modal>
    </div>
  )
}

function Message({ message, onCitation, onFollowUp }) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-brand px-4 py-2.5 text-[14px] leading-relaxed text-white">
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div className="animate-fade-up">
      <div className="flex gap-3">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-brand/12 text-[11px] font-bold text-brand">
          AI
        </span>
        <div className="min-w-0 flex-1">
          {message.found_answer === false && !message.isError && (
            <div className="mb-2.5 inline-flex items-center gap-1.5 rounded-lg border border-warn/40 bg-warn/10 px-2.5 py-1 text-[11.5px] font-medium text-ink">
              <span aria-hidden="true" className="font-bold text-warn">!</span>
              Not found in your documents
            </div>
          )}

          <Markdown text={message.content} onCitation={onCitation} />

          <SourceList sources={message.sources} compact />
          <RetrievalTrace retrieval={message.retrieval} />

          {message.follow_ups?.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {message.follow_ups.map((question) => (
                <button
                  key={question}
                  onClick={() => onFollowUp(question)}
                  className="rounded-full border border-line px-3 py-1.5 text-[12px] text-muted transition-all hover:border-brand/50 hover:text-ink"
                >
                  {question}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
