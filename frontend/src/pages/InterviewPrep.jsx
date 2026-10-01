import { useState } from 'react'
import { useApp } from '../context/AppContext'
import * as api from '../services/api'
import { useAnalysis } from '../hooks/useAnalysis'
import { PageHeader, PageState, RefreshingBar } from '../components/PageState'
import { SourceList } from '../components/Sources'
import { Badge, Button, Card, CardBody, CardHeader, Tab, TabList, TabPanel, Tabs, cx } from '../components/ui'

const DIFFICULTY = {
  easy: { tone: 'good', label: 'Easy' },
  medium: { tone: 'warn', label: 'Medium' },
  hard: { tone: 'critical', label: 'Hard' },
}

export default function InterviewPrep() {
  const { sessionId, toastError } = useApp()
  const { data, loading, error, run, refresh } = useAnalysis(api.getInterview)
  const [tab, setTab] = useState('all')
  const [open, setOpen] = useState({})
  const [focus, setFocus] = useState('')
  const [regenerating, setRegenerating] = useState(false)

  const regenerate = async () => {
    setRegenerating(true)
    try {
      await api.regenerateInterview(sessionId, { focus: focus.trim() || null, refresh: true })
      await run(false)
      setFocus('')
    } catch (caught) {
      toastError(caught)
    } finally {
      setRegenerating(false)
    }
  }

  const categories = data?.categories || []
  const visible =
    tab === 'all'
      ? data?.questions || []
      : (data?.questions || []).filter((question) => question.category === tab)

  return (
    <div className="space-y-6">
      <PageHeader
        title="Interview preparation"
        subtitle="Technical questions come from what the job requires. Project and experience questions come from what's actually in your resume."
        action={
          data && (
            <Button size="sm" variant="secondary" onClick={refresh} loading={loading}>
              Regenerate
            </Button>
          )
        }
      />

      <RefreshingBar show={(loading && Boolean(data)) || regenerating} label="Writing your question set..." />

      <PageState loading={loading} error={error} onRetry={() => run(false)} data={data}>
        {data && (
          <div className="space-y-5">
            {/* --------------------------------------------- focus first */}
            {data.preparation_focus?.length > 0 && (
              <Card className="border-brand/25 bg-brand/[0.04]">
                <CardHeader
                  title="Revise these first"
                  subtitle="Ordered by how likely they are to come up in this interview."
                />
                <CardBody>
                  <ol className="space-y-2.5">
                    {data.preparation_focus.map((item, index) => (
                      <li key={index} className="flex gap-3 text-[13.5px] leading-relaxed text-ink">
                        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand/15 text-[11px] font-bold text-brand">
                          {index + 1}
                        </span>
                        {item}
                      </li>
                    ))}
                  </ol>
                </CardBody>
              </Card>
            )}

            {/* ------------------------------------------ focused rebuild */}
            <Card className="card-pad">
              <p className="text-[13px] font-semibold text-ink">Want questions on a specific topic?</p>
              <div className="mt-2.5 flex flex-col gap-2 sm:flex-row">
                <input
                  value={focus}
                  onChange={(event) => setFocus(event.target.value)}
                  onKeyDown={(event) => event.key === 'Enter' && regenerate()}
                  placeholder="e.g. REST API design, or my NutriSmart project"
                  className="h-10 flex-1 rounded-xl border border-line bg-surface px-3.5 text-[13.5px] text-ink placeholder:text-subtle focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/25"
                />
                <Button onClick={regenerate} loading={regenerating} disabled={!focus.trim()}>
                  Generate
                </Button>
              </div>
            </Card>

            {/* ------------------------------------------------- questions */}
            <Tabs value={tab} onChange={setTab}>
              <TabList>
                <Tab id="all" count={data.questions?.length ?? 0}>All</Tab>
                {categories.map((category) => (
                  <Tab key={category.key} id={category.key} count={category.count}>
                    {category.label}
                  </Tab>
                ))}
              </TabList>

              <TabPanel id={tab}>
                {visible.length === 0 ? (
                  <Card className="card-pad">
                    <p className="text-[13.5px] text-muted">No questions in this category.</p>
                  </Card>
                ) : (
                  <ul className="space-y-3">
                    {visible.map((question) => {
                      const expanded = open[question.id]
                      const difficulty = DIFFICULTY[question.difficulty] || DIFFICULTY.medium
                      return (
                        <li key={question.id}>
                          <Card>
                            <button
                              onClick={() =>
                                setOpen((current) => ({ ...current, [question.id]: !current[question.id] }))
                              }
                              className="flex w-full items-start gap-3 px-5 py-4 text-left sm:px-6"
                              aria-expanded={Boolean(expanded)}
                            >
                              <svg
                                className={cx(
                                  'mt-1 h-3.5 w-3.5 shrink-0 text-subtle transition-transform',
                                  expanded && 'rotate-90'
                                )}
                                viewBox="0 0 12 12"
                                fill="currentColor"
                              >
                                <path d="M4 2l5 4-5 4z" />
                              </svg>
                              <div className="min-w-0 flex-1">
                                <p className="text-[14px] font-medium leading-relaxed text-ink">
                                  {question.question}
                                </p>
                                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                                  <Badge tone="brand">{question.category_label}</Badge>
                                  <Badge tone={difficulty.tone}>{difficulty.label}</Badge>
                                  {question.related_to && (
                                    <span className="text-[11.5px] text-subtle">
                                      on {question.related_to}
                                    </span>
                                  )}
                                </div>
                              </div>
                            </button>

                            {expanded && (
                              <CardBody className="animate-fade-up space-y-4 border-t border-line pt-4">
                                {question.expected_points?.length > 0 && (
                                  <div>
                                    <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-subtle">
                                      A strong answer covers
                                    </p>
                                    <ul className="space-y-1.5">
                                      {question.expected_points.map((point, index) => (
                                        <li
                                          key={index}
                                          className="flex gap-2.5 text-[13px] leading-relaxed text-muted"
                                        >
                                          <span aria-hidden="true" className="mt-0.5 text-good">✓</span>
                                          {point}
                                        </li>
                                      ))}
                                    </ul>
                                  </div>
                                )}

                                {question.sample_answer && (
                                  <div className="rounded-xl border border-line bg-raised/40 p-3.5">
                                    <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-subtle">
                                      Sample answer
                                    </p>
                                    <p className="text-[13px] leading-relaxed text-ink">
                                      {question.sample_answer}
                                    </p>
                                    <p className="mt-2.5 text-[11.5px] leading-relaxed text-subtle">
                                      Anything in [brackets] is a detail only you can supply — it was
                                      deliberately left blank rather than made up.
                                    </p>
                                  </div>
                                )}
                              </CardBody>
                            )}
                          </Card>
                        </li>
                      )
                    })}
                  </ul>
                )}
              </TabPanel>
            </Tabs>

            {data.dropped_unverified > 0 && (
              <p className="text-[12px] leading-relaxed text-subtle">
                {data.dropped_unverified} generated question{data.dropped_unverified === 1 ? ' was' : 's were'}{' '}
                discarded for referring to a project that isn't in your resume.
              </p>
            )}

            <SourceList sources={data.sources} title="Passages these questions were built from" />
          </div>
        )}
      </PageState>
    </div>
  )
}
