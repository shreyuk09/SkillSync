import { useState } from 'react'
import { useApp } from '../context/AppContext'
import * as api from '../services/api'
import { useAnalysis } from '../hooks/useAnalysis'
import { PageHeader, PageState, RefreshingBar } from '../components/PageState'
import { SourceList } from '../components/Sources'
import { Badge, Button, Card, CardBody, CardHeader, Progress, cx } from '../components/ui'

const PRIORITY_TONE = { high: 'critical', medium: 'warn', low: 'neutral' }
const LEVELS = ['none', 'aware', 'basic', 'practical', 'confident']

function levelPercent(level) {
  const index = LEVELS.indexOf(level)
  return index < 0 ? 0 : (index / (LEVELS.length - 1)) * 100
}

export default function Roadmap() {
  const { sessionId, toastError } = useApp()
  const { data, loading, error, run, refresh } = useAnalysis(api.getRoadmap)
  const [weeks, setWeeks] = useState(0)
  const [rebuilding, setRebuilding] = useState(false)
  const [done, setDone] = useState({})

  const rebuild = async (targetWeeks) => {
    setRebuilding(true)
    try {
      await api.regenerateRoadmap(sessionId, { weeks: targetWeeks, refresh: true })
      await run(false)
      setWeeks(targetWeeks)
    } catch (caught) {
      toastError(caught)
    } finally {
      setRebuilding(false)
    }
  }

  const completed = Object.values(done).filter(Boolean).length
  const total = data?.weeks?.length ?? 0

  return (
    <div className="space-y-6">
      <PageHeader
        title="Learning roadmap"
        subtitle="Built only from the gaps this analysis actually found — not a generic curriculum."
        action={
          data && !data.no_gaps && (
            <Button size="sm" variant="secondary" onClick={refresh} loading={loading}>
              Rebuild
            </Button>
          )
        }
      />

      <RefreshingBar show={(loading && Boolean(data)) || rebuilding} label="Planning your weeks..." />

      <PageState loading={loading} error={error} onRetry={() => run(false)} data={data}>
        {data && (
          <div className="space-y-5">
            {data.no_gaps ? (
              <Card className="border-good/30 card-pad">
                <p className="flex items-center gap-2 text-[15px] font-semibold text-ink">
                  <span aria-hidden="true" className="text-good">✓</span>
                  No skill gaps to close
                </p>
                <p className="mt-2 text-[13.5px] leading-relaxed text-muted">{data.summary}</p>
              </Card>
            ) : (
              <>
                {/* ------------------------------------------------ header */}
                <Card className="card-pad">
                  <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0 flex-1">
                      <p className="text-[11px] font-semibold uppercase tracking-wider text-subtle">
                        Target role
                      </p>
                      <h2 className="mt-1 text-[20px] font-bold tracking-tight text-ink">
                        {data.target_role || 'This role'}
                      </h2>
                      <p className="mt-2.5 text-[13.5px] leading-relaxed text-muted">{data.summary}</p>
                      {data.gap_counts && (
                        <div className="mt-3.5 flex flex-wrap gap-1.5">
                          <Badge tone="critical">
                            {data.gap_counts.required_missing} required skills missing
                          </Badge>
                          <Badge tone="warn">
                            {data.gap_counts.partial} skills need evidence
                          </Badge>
                          <Badge>{data.gap_counts.preferred_missing} preferred missing</Badge>
                        </div>
                      )}
                    </div>

                    <div className="shrink-0 lg:w-56">
                      <div className="rounded-xl border border-line bg-raised/40 p-4">
                        <p className="text-[11px] font-semibold uppercase tracking-wider text-subtle">
                          Plan length
                        </p>
                        <p className="mt-1 text-[26px] font-bold leading-none tabular-nums text-ink">
                          {data.duration_weeks}
                          <span className="ml-1 text-[14px] font-semibold text-muted">weeks</span>
                        </p>
                        <div className="mt-3 flex gap-1.5">
                          {[4, 6, 8].map((option) => (
                            <button
                              key={option}
                              onClick={() => rebuild(option)}
                              disabled={rebuilding}
                              className={cx(
                                'flex-1 rounded-lg border px-2 py-1.5 text-[12px] font-medium transition-colors disabled:opacity-50',
                                weeks === option
                                  ? 'border-brand bg-brand/10 text-brand'
                                  : 'border-line text-muted hover:border-brand/40 hover:text-ink'
                              )}
                            >
                              {option}w
                            </button>
                          ))}
                        </div>
                      </div>

                      {total > 0 && (
                        <div className="mt-3">
                          <div className="flex items-baseline justify-between">
                            <span className="text-[11.5px] text-subtle">Your progress</span>
                            <span className="text-[12px] font-semibold tabular-nums text-ink">
                              {completed}/{total}
                            </span>
                          </div>
                          <Progress
                            className="mt-1.5"
                            value={total ? (completed / total) * 100 : 0}
                            tone="good"
                          />
                        </div>
                      )}
                    </div>
                  </div>
                </Card>

                {/* ---------------------------------------- skills to learn */}
                {data.skills?.length > 0 && (
                  <Card>
                    <CardHeader
                      title="Skills this plan covers"
                      subtitle="Every one of these was flagged as missing or weak by the match analysis."
                    />
                    <CardBody>
                      <ul className="space-y-4">
                        {data.skills.map((skill) => (
                          <li key={skill.skill}>
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <span className="flex items-center gap-2">
                                <span className="text-[14px] font-semibold text-ink">{skill.skill}</span>
                                <Badge tone={PRIORITY_TONE[skill.priority]}>
                                  {skill.priority} priority
                                </Badge>
                              </span>
                              <span className="text-[12px] text-subtle">
                                {skill.current_level} → {skill.target_level}
                              </span>
                            </div>
                            <div className="mt-2 flex items-center gap-2">
                              <Progress value={levelPercent(skill.current_level)} className="flex-1" />
                              <span aria-hidden="true" className="text-[11px] text-subtle">→</span>
                              <Progress
                                value={levelPercent(skill.target_level)}
                                tone="good"
                                className="flex-1"
                              />
                            </div>
                            {skill.why && (
                              <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted">{skill.why}</p>
                            )}
                          </li>
                        ))}
                      </ul>
                    </CardBody>
                  </Card>
                )}

                {/* ------------------------------------------ week timeline */}
                <div className="space-y-3">
                  {(data.weeks || []).map((week) => (
                    <Card
                      key={week.week}
                      className={cx('transition-all', done[week.week] && 'border-good/40')}
                    >
                      <div className="flex items-start gap-4 px-5 pt-5 sm:px-6">
                        <button
                          onClick={() =>
                            setDone((current) => ({ ...current, [week.week]: !current[week.week] }))
                          }
                          aria-pressed={Boolean(done[week.week])}
                          aria-label={`Mark week ${week.week} as done`}
                          className={cx(
                            'mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border text-[12px] font-bold transition-colors',
                            done[week.week]
                              ? 'border-good bg-good/15 text-good'
                              : 'border-line text-subtle hover:border-brand hover:text-brand'
                          )}
                        >
                          {done[week.week] ? '✓' : week.week}
                        </button>

                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="text-[15px] font-semibold text-ink">
                              Week {week.week}: {week.focus}
                            </h3>
                            {week.hours ? <Badge>{week.hours} hrs</Badge> : null}
                          </div>
                          {week.skills?.length > 0 && (
                            <div className="mt-2 flex flex-wrap gap-1.5">
                              {week.skills.map((skill) => (
                                <Badge key={skill} tone="brand">{skill}</Badge>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>

                      <CardBody className="space-y-4">
                        {week.goals?.length > 0 && (
                          <div>
                            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-subtle">
                              Goals
                            </p>
                            <ul className="space-y-1.5">
                              {week.goals.map((goal, index) => (
                                <li
                                  key={index}
                                  className="flex gap-2.5 text-[13px] leading-relaxed text-muted"
                                >
                                  <span aria-hidden="true" className="mt-0.5 text-brand">·</span>
                                  {goal}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {week.project && (
                          <div className="rounded-xl border border-brand/25 bg-brand/[0.05] p-3.5">
                            <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-brand">
                              Build this — then put it on your resume
                            </p>
                            <p className="text-[13px] leading-relaxed text-ink">{week.project}</p>
                          </div>
                        )}

                        {week.resources?.length > 0 && (
                          <div>
                            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-subtle">
                              Where to learn it
                            </p>
                            <ul className="space-y-1.5">
                              {week.resources.map((resource, index) => (
                                <li key={index} className="text-[12.5px] leading-relaxed text-muted">
                                  {resource}
                                </li>
                              ))}
                            </ul>
                            <p className="mt-2 text-[11.5px] leading-relaxed text-subtle">
                              Resource types are suggested, not specific links — search for the current
                              official docs rather than trusting a URL an AI produced.
                            </p>
                          </div>
                        )}
                      </CardBody>
                    </Card>
                  ))}
                </div>

                {data.after_roadmap?.length > 0 && (
                  <Card className="border-good/30">
                    <CardHeader
                      title="When you finish, your resume should say"
                      subtitle="These are the lines this plan is designed to earn you."
                    />
                    <CardBody>
                      <ul className="space-y-2">
                        {data.after_roadmap.map((item, index) => (
                          <li
                            key={index}
                            className="flex gap-2.5 text-[13px] leading-relaxed text-muted"
                          >
                            <span aria-hidden="true" className="mt-0.5 text-good">✓</span>
                            {item}
                          </li>
                        ))}
                      </ul>
                    </CardBody>
                  </Card>
                )}

                <SourceList sources={data.sources} title="Passages this plan was built from" />
              </>
            )}
          </div>
        )}
      </PageState>
    </div>
  )
}
