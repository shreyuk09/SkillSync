import { useNavigate } from 'react-router-dom'
import * as api from '../services/api'
import { useAnalysis } from '../hooks/useAnalysis'
import { ComponentBars, RelevanceRow, ScoreRing, StatTile } from '../components/charts'
import { PageHeader, PageState, RefreshingBar } from '../components/PageState'
import { SourceList } from '../components/Sources'
import {
  Badge, Button, Card, CardBody, CardHeader, InfoTip, StatusPill, cx,
} from '../components/ui'

const BAND_COPY = {
  strong: 'Strong match',
  good: 'Good match',
  moderate: 'Moderate match',
  weak: 'Weak match',
}

export default function Dashboard() {
  const navigate = useNavigate()
  const { data, loading, error, run, refresh } = useAnalysis(api.getDashboard)

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        subtitle={
          data
            ? `${data.candidate?.name || 'Your resume'} vs ${data.job?.title || 'this role'}${data.job?.company ? ` at ${data.job.company}` : ''}`
            : 'Your overall compatibility with this role, and where the score comes from.'
        }
        action={
          data && (
            <Button variant="secondary" size="sm" onClick={refresh} loading={loading}>
              Re-analyse
            </Button>
          )
        }
      />

      <RefreshingBar show={loading && Boolean(data)} />

      <PageState loading={loading} error={error} onRetry={() => run(false)} data={data}>
        {data && (
          <div className="space-y-5">
            {/* ------------------------------------------- hero: the score */}
            <Card className="card-pad">
              <div className="flex flex-col items-center gap-7 lg:flex-row lg:items-start">
                <div className="flex flex-col items-center">
                  <ScoreRing value={data.overall} band={BAND_COPY[data.verdict_band]} />
                  <p className="mt-3 max-w-[180px] text-center text-[12px] leading-relaxed text-subtle">
                    Weighted across five components
                  </p>
                </div>

                <div className="min-w-0 flex-1">
                  {data.verdict ? (
                    <p className="text-[15px] leading-relaxed text-ink">{data.verdict}</p>
                  ) : (
                    <p className="text-[15px] leading-relaxed text-muted">
                      Scores are computed. The written explanation needs an API key.
                    </p>
                  )}

                  <div className="mt-5">
                    <ComponentBars
                      components={data.components}
                      onSelect={() => navigate('/match')}
                    />
                  </div>

                  <details className="group mt-5">
                    <summary className="cursor-pointer list-none text-[12.5px] font-medium text-muted transition-colors hover:text-brand">
                      <span className="inline-flex items-center gap-1.5">
                        <svg
                          className="h-3 w-3 transition-transform group-open:rotate-90"
                          viewBox="0 0 12 12"
                          fill="currentColor"
                        >
                          <path d="M4 2l5 4-5 4z" />
                        </svg>
                        Show the exact formula
                      </span>
                    </summary>
                    <div className="scroll-x mt-2.5 rounded-xl border border-line bg-raised/40 p-3.5">
                      <p className="whitespace-nowrap font-mono text-[11.5px] text-muted">
                        {data.formula}
                      </p>
                    </div>
                    <p className="mt-2 text-[12px] leading-relaxed text-subtle">
                      {data.method?.note}
                    </p>
                  </details>
                </div>
              </div>
            </Card>

            {/* ------------------------------------------------ stat tiles */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatTile
                label="Skills matched"
                value={data.skills.matched.length}
                suffix={`/ ${data.skills.matched.length + data.skills.partial.length + data.skills.missing.length}`}
                caption={`${data.skills.partial.length} partial · ${data.skills.missing.length} missing`}
                tone={data.skills.missing.length === 0 ? 'good' : 'neutral'}
              />
              <StatTile
                label="ATS keywords"
                value={data.ats.score}
                suffix="%"
                caption={`${data.ats.matched_count} of ${data.ats.total} job keywords appear in your resume`}
                tone={data.ats.score >= 70 ? 'good' : data.ats.score >= 45 ? 'warn' : 'critical'}
              />
              <StatTile
                label="Top project fit"
                value={data.projects?.[0]?.relevance ?? 0}
                suffix="%"
                caption={data.projects?.[0]?.name || 'No projects found in your resume'}
              />
              <StatTile
                label="Resume completeness"
                value={data.candidate?.completeness?.score ?? 0}
                suffix="%"
                caption={
                  data.candidate?.completeness?.missing?.length
                    ? `Missing: ${data.candidate.completeness.missing.slice(0, 2).join(', ')}`
                    : 'All standard sections present'
                }
              />
            </div>

            {/* -------------------------------------- strengths &amp; gaps */}
            <div className="grid gap-5 lg:grid-cols-2">
              <Card>
                <CardHeader
                  title="What's working"
                  subtitle="Genuine strengths, each backed by a passage from your documents."
                />
                <CardBody>
                  {data.strengths?.length ? (
                    <ul className="space-y-3.5">
                      {data.strengths.map((item, index) => (
                        <li key={index} className="flex gap-3">
                          <span
                            aria-hidden="true"
                            className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-good/15 text-[11px] font-bold text-good"
                          >
                            ✓
                          </span>
                          <div className="min-w-0">
                            <p className="text-[13.5px] font-semibold text-ink">{item.title}</p>
                            <p className="mt-1 text-[13px] leading-relaxed text-muted">{item.detail}</p>
                            {item.evidence && (
                              <p className="mt-1.5 border-l-2 border-line pl-2.5 text-[12.5px] italic leading-relaxed text-subtle">
                                {item.evidence}
                              </p>
                            )}
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-[13px] text-muted">
                      No written strengths available — the score components above still apply.
                    </p>
                  )}
                </CardBody>
              </Card>

              <Card>
                <CardHeader
                  title="What's holding you back"
                  subtitle="Ordered by how much each gap affects this application."
                />
                <CardBody>
                  {data.gaps?.length ? (
                    <ul className="space-y-3.5">
                      {data.gaps.map((item, index) => (
                        <li key={index} className="flex gap-3">
                          <span
                            aria-hidden="true"
                            className={cx(
                              'mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold',
                              item.severity === 'high'
                                ? 'bg-critical/15 text-critical'
                                : item.severity === 'medium'
                                  ? 'bg-warn/20 text-warn'
                                  : 'bg-raised text-subtle'
                            )}
                          >
                            !
                          </span>
                          <div className="min-w-0">
                            <p className="flex flex-wrap items-center gap-2 text-[13.5px] font-semibold text-ink">
                              {item.title}
                              <Badge
                                tone={
                                  item.severity === 'high'
                                    ? 'critical'
                                    : item.severity === 'medium'
                                      ? 'warn'
                                      : 'neutral'
                                }
                              >
                                {item.severity} priority
                              </Badge>
                            </p>
                            <p className="mt-1 text-[13px] leading-relaxed text-muted">{item.detail}</p>
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-[13px] text-muted">No significant gaps were found.</p>
                  )}
                </CardBody>
              </Card>
            </div>

            {/* -------------------------------------------- skills summary */}
            <Card>
              <CardHeader
                title="Skills at a glance"
                subtitle="Present means the resume shows you using it. Partial means it's claimed but not demonstrated."
                action={
                  <Button size="sm" variant="ghost" onClick={() => navigate('/match')}>
                    Full breakdown →
                  </Button>
                }
              />
              <CardBody className="space-y-4">
                {[
                  { key: 'matched', label: 'Present', items: data.skills.matched },
                  { key: 'partial', label: 'Partially matched', items: data.skills.partial },
                  { key: 'missing', label: 'Missing', items: data.skills.missing },
                ].map((group) =>
                  group.items.length ? (
                    <div key={group.key}>
                      <p className="mb-2 text-[11.5px] font-semibold uppercase tracking-wider text-subtle">
                        {group.label} · {group.items.length}
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {group.items.map((item) => (
                          <StatusPill key={item.skill} status={group.key}>
                            {item.skill}
                          </StatusPill>
                        ))}
                      </div>
                    </div>
                  ) : null
                )}
              </CardBody>
            </Card>

            {/* ------------------------------------------ project relevance */}
            {data.projects?.length > 0 && (
              <Card>
                <CardHeader
                  title="Project relevance"
                  icon={
                    <InfoTip text="Each project's text is embedded and compared against the job's responsibilities and required skills. The percentage is the average similarity to its closest requirements — no LLM decides this number." />
                  }
                  subtitle="Ranked by embedding similarity to what this job actually involves."
                  action={
                    <Button size="sm" variant="ghost" onClick={() => navigate('/match')}>
                      Why? →
                    </Button>
                  }
                />
                <CardBody className="space-y-5">
                  {data.projects.map((project, index) => (
                    <RelevanceRow
                      key={project.name}
                      rank={index + 1}
                      name={project.name}
                      value={project.relevance}
                      detail={project.calculation}
                    />
                  ))}
                </CardBody>
              </Card>
            )}

            {/* ---------------------------------------------- next actions */}
            <div className="grid gap-4 sm:grid-cols-3">
              {[
                { to: '/improvements', title: 'Fix your resume', body: 'Before/after rewrites for this exact job.' },
                { to: '/interview', title: 'Prepare for the interview', body: 'Questions built from your real projects.' },
                { to: '/roadmap', title: 'Close the skill gaps', body: 'A week-by-week plan for what you are missing.' },
              ].map((cta) => (
                <button
                  key={cta.to}
                  onClick={() => navigate(cta.to)}
                  className="card card-pad text-left transition-all hover:border-brand/40 hover:shadow-lift"
                >
                  <p className="text-[14px] font-semibold text-ink">{cta.title}</p>
                  <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted">{cta.body}</p>
                  <span className="mt-3 inline-flex items-center gap-1 text-[12.5px] font-medium text-brand">
                    Open
                    <svg className="h-3 w-3" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <path d="M4 10h12M11 5l5 5-5 5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </span>
                </button>
              ))}
            </div>

            <SourceList
              sources={data.sources}
              title="Passages retrieved for this analysis"
              emptyNote="No sources were cited for the written summary."
            />
          </div>
        )}
      </PageState>
    </div>
  )
}
