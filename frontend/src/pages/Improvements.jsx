import { useEffect, useState } from 'react'
import { useApp } from '../context/AppContext'
import * as api from '../services/api'
import { useAnalysis } from '../hooks/useAnalysis'
import { PageHeader, PageState, RefreshingBar } from '../components/PageState'
import { SourceList } from '../components/Sources'
import { Badge, Button, Card, CardBody, CardHeader, cx } from '../components/ui'

// High / Medium / Low, colour-coded so the priority reads at a glance.
const IMPACT_TONE = { high: 'critical', medium: 'warn', low: 'neutral' }
const IMPACT_LABEL = { high: 'High', medium: 'Medium', low: 'Low' }

export default function Improvements() {
  const { sessionId, toast, toastError } = useApp()
  const { data, loading, error, run, refresh } = useAnalysis(api.getImprovements)
  const [decisions, setDecisions] = useState({})
  const [copied, setCopied] = useState('')

  useEffect(() => {
    if (!data?.suggestions) return
    const initial = {}
    data.suggestions.forEach((item) => {
      initial[item.id] = item.decision || 'pending'
    })
    setDecisions(initial)
  }, [data])

  const decide = async (id, decision) => {
    const next = decisions[id] === decision ? 'pending' : decision
    setDecisions((current) => ({ ...current, [id]: next }))
    try {
      await api.setImprovementDecision(sessionId, id, next)
    } catch (caught) {
      toastError(caught)
    }
  }

  const copy = async (id, text) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(id)
      setTimeout(() => setCopied(''), 1600)
    } catch {
      toast('Copying failed — select the text and copy it manually.', { type: 'error' })
    }
  }

  const accepted = Object.values(decisions).filter((value) => value === 'accepted').length
  const rejected = Object.values(decisions).filter((value) => value === 'rejected').length

  return (
    <div className="space-y-6">
      <PageHeader
        title="Resume improvements"
        subtitle="Rewrites for this specific job. Every fact stays exactly as you wrote it — nothing is added that your resume doesn't already say."
        action={
          data && (
            <Button size="sm" variant="secondary" onClick={refresh} loading={loading}>
              Regenerate
            </Button>
          )
        }
      />

      <RefreshingBar show={loading && Boolean(data)} label="Writing new suggestions..." />

      <PageState loading={loading} error={error} onRetry={() => run(false)} data={data}>
        {data && (
          <div className="space-y-5">
            <Card className="card-pad">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="flex gap-6">
                  {[
                    { label: 'Suggestions', value: data.suggestions?.length ?? 0 },
                    { label: 'Accepted', value: accepted },
                    { label: 'Rejected', value: rejected },
                  ].map((stat) => (
                    <div key={stat.label}>
                      <p className="text-[22px] font-bold leading-none tabular-nums text-ink">
                        {stat.value}
                      </p>
                      <p className="mt-1 text-[11px] uppercase tracking-wider text-subtle">
                        {stat.label}
                      </p>
                    </div>
                  ))}
                </div>
                <p className="max-w-md text-[12.5px] leading-relaxed text-muted">{data.note}</p>
              </div>
            </Card>

            {data.suggestions?.length === 0 ? (
              <Card className="card-pad">
                <p className="text-[13.5px] leading-relaxed text-muted">
                  No verifiable rewrite suggestions were produced. That usually means the resume
                  text couldn't be quoted back exactly — try re-uploading it as a text-based PDF or
                  pasting the content directly.
                </p>
              </Card>
            ) : (
              <ul className="space-y-4">
                {(data.suggestions || []).map((suggestion) => {
                  const decision = decisions[suggestion.id] || 'pending'
                  return (
                    <li key={suggestion.id}>
                      <Card
                        className={cx(
                          'transition-all',
                          decision === 'accepted' && 'border-good/40',
                          decision === 'rejected' && 'opacity-60'
                        )}
                      >
                        <CardHeader
                          title={suggestion.what_to_fix || suggestion.section}
                          action={
                            <div className="flex items-center gap-1.5">
                              <Badge tone={IMPACT_TONE[suggestion.impact]}>
                                {IMPACT_LABEL[suggestion.impact] || suggestion.impact} impact
                              </Badge>
                            </div>
                          }
                        />
                        <CardBody className="space-y-3.5">
                          {/* -------------------------------- why it matters */}
                          {(suggestion.why_it_matters || suggestion.reason) && (
                            <p className="flex items-start gap-2 text-[13px] leading-relaxed text-muted">
                              <span
                                aria-hidden="true"
                                className="mt-[3px] shrink-0 text-[11px] font-bold uppercase tracking-wider text-subtle"
                              >
                                Why
                              </span>
                              <span>{suggestion.why_it_matters || suggestion.reason}</span>
                            </p>
                          )}

                          <p className="text-[11.5px] text-subtle">
                            In your <strong className="text-muted">{suggestion.section}</strong> section
                          </p>
                          {/* ------------------------------ before / after */}
                          <div className="grid gap-3 lg:grid-cols-2">
                            <div className="rounded-xl border border-line bg-raised/40 p-3.5">
                              <p className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-subtle">
                                <span aria-hidden="true">−</span> Before — your current line
                              </p>
                              <p className="text-[13px] leading-relaxed text-muted">
                                {suggestion.original}
                              </p>
                            </div>
                            <div className="rounded-xl border border-good/30 bg-good/[0.05] p-3.5">
                              <p className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-subtle">
                                <span aria-hidden="true" className="text-good">+</span> After — copy this
                              </p>
                              <p className="text-[13px] leading-relaxed text-ink">
                                {suggestion.suggested}
                              </p>
                            </div>
                          </div>

                          {/* ------------------- what the model needs from you */}
                          {suggestion.information_needed?.length > 0 && (
                            <div className="rounded-xl border border-warn/35 bg-warn/[0.06] p-3.5">
                              <p className="mb-1.5 flex items-center gap-1.5 text-[12px] font-semibold text-ink">
                                <span aria-hidden="true" className="font-bold text-warn">?</span>
                                To make this stronger, we'd need from you:
                              </p>
                              <ul className="ml-4 list-disc space-y-1">
                                {suggestion.information_needed.map((item, index) => (
                                  <li key={index} className="text-[12.5px] leading-relaxed text-muted">
                                    {item}
                                  </li>
                                ))}
                              </ul>
                              <p className="mt-2 text-[11.5px] leading-relaxed text-subtle">
                                These were left as placeholders rather than invented.
                              </p>
                            </div>
                          )}

                          {/* ---------------------------------------- actions */}
                          <div className="flex flex-wrap items-center gap-2 border-t border-line pt-3.5">
                            <Button
                              size="sm"
                              variant={decision === 'accepted' ? 'primary' : 'secondary'}
                              onClick={() => decide(suggestion.id, 'accepted')}
                            >
                              <span aria-hidden="true">✓</span>
                              {decision === 'accepted' ? 'Accepted' : 'Accept'}
                            </Button>
                            <Button
                              size="sm"
                              variant={decision === 'rejected' ? 'danger' : 'secondary'}
                              onClick={() => decide(suggestion.id, 'rejected')}
                            >
                              <span aria-hidden="true">✗</span>
                              {decision === 'rejected' ? 'Rejected' : 'Reject'}
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => copy(suggestion.id, suggestion.suggested)}
                            >
                              {copied === suggestion.id ? 'Copied' : 'Copy suggestion'}
                            </Button>
                          </div>
                        </CardBody>
                      </Card>
                    </li>
                  )
                })}
              </ul>
            )}

            {/* ------------------------------------------ accepted summary */}
            {accepted > 0 && (
              <Card className="border-good/30">
                <CardHeader
                  title={`Your ${accepted} accepted rewrite${accepted === 1 ? '' : 's'}`}
                  subtitle="Copy these into your resume."
                  action={
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() =>
                        copy(
                          'all',
                          data.suggestions
                            .filter((item) => decisions[item.id] === 'accepted')
                            .map((item) => `${item.section}: ${item.suggested}`)
                            .join('\n\n')
                        )
                      }
                    >
                      {copied === 'all' ? 'Copied' : 'Copy all'}
                    </Button>
                  }
                />
                <CardBody>
                  <ul className="space-y-3">
                    {data.suggestions
                      .filter((item) => decisions[item.id] === 'accepted')
                      .map((item) => (
                        <li key={item.id} className="border-l-2 border-good/50 pl-3.5">
                          <p className="text-[11px] font-semibold uppercase tracking-wider text-subtle">
                            {item.section}
                          </p>
                          <p className="mt-1 text-[13px] leading-relaxed text-ink">{item.suggested}</p>
                        </li>
                      ))}
                  </ul>
                </CardBody>
              </Card>
            )}

            {data.formatting_notes?.length > 0 && (
              <Card>
                <CardHeader
                  title="Formatting and structure"
                  subtitle="Not about wording — about how the document is put together."
                />
                <CardBody>
                  <ul className="space-y-2">
                    {data.formatting_notes.map((note, index) => (
                      <li key={index} className="flex gap-2.5 text-[13px] leading-relaxed text-muted">
                        <span aria-hidden="true" className="text-brand">·</span>
                        {note}
                      </li>
                    ))}
                  </ul>
                </CardBody>
              </Card>
            )}

            <SourceList sources={data.sources} title="Passages these suggestions were written from" />
          </div>
        )}
      </PageState>
    </div>
  )
}
