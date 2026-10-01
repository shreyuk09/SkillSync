import { useState } from 'react'
import * as api from '../services/api'
import { useAnalysis } from '../hooks/useAnalysis'
import { ComponentBars, KeywordGrid, RelevanceRow, ScoreRing } from '../components/charts'
import { PageHeader, PageState, RefreshingBar } from '../components/PageState'
import { SourceList } from '../components/Sources'
import {
  Badge, Button, Card, CardBody, CardHeader, InfoTip, StatusPill,
  Tab, TabList, TabPanel, Tabs, cx,
} from '../components/ui'

export default function MatchAnalysis() {
  const [tab, setTab] = useState('scores')
  const { data, loading, error, run, refresh } = useAnalysis(api.getMatch)
  const projects = useAnalysis(api.getProjects, { auto: true })
  const priorities = useAnalysis(api.getPriorities, { auto: true })

  const skills = data?.skills
  const ats = data?.ats

  return (
    <div className="space-y-6">
      <PageHeader
        title="Match analysis"
        subtitle="Every number here is computed by the backend and shows its own arithmetic. The AI explains the scores; it doesn't choose them."
        action={
          data && (
            <Button size="sm" variant="secondary" onClick={refresh} loading={loading}>
              Re-analyse
            </Button>
          )
        }
      />

      <RefreshingBar show={loading && Boolean(data)} />

      <PageState loading={loading} error={error} onRetry={() => run(false)} data={data}>
        {data && (
          <Tabs value={tab} onChange={setTab}>
            <TabList>
              <Tab id="scores">Score breakdown</Tab>
              <Tab id="skills" count={(skills?.matched.length ?? 0) + (skills?.partial.length ?? 0) + (skills?.missing.length ?? 0)}>
                Skills
              </Tab>
              <Tab id="keywords" count={ats?.total}>ATS keywords</Tab>
              <Tab id="projects" count={data.projects?.length}>Projects</Tab>
              <Tab id="actions">What should I change?</Tab>
            </TabList>

            {/* ================================================== SCORES */}
            <TabPanel id="scores">
              <div className="space-y-5">
                <Card className="card-pad">
                  <div className="flex flex-col items-center gap-7 lg:flex-row lg:items-start">
                    <ScoreRing value={data.overall} band={data.verdict_band} />
                    <div className="min-w-0 flex-1">
                      {data.verdict && (
                        <p className="mb-5 text-[15px] leading-relaxed text-ink">{data.verdict}</p>
                      )}
                      <ComponentBars components={data.components} />
                    </div>
                  </div>
                </Card>

                {/* One card per component, each with its arithmetic. */}
                <div className="grid gap-4 lg:grid-cols-2">
                  {data.components.map((component) => (
                    <Card key={component.key}>
                      <CardHeader
                        title={component.label}
                        subtitle={`Worth ${component.weight_percent}% of the overall score`}
                        action={
                          <span className="text-[20px] font-bold tabular-nums text-ink">
                            {component.score}%
                          </span>
                        }
                      />
                      <CardBody className="space-y-3">
                        <div>
                          <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-subtle">
                            How this was calculated
                          </p>
                          <p className="text-[13px] leading-relaxed text-muted">
                            {component.calculation}
                          </p>
                        </div>
                        {data.explanations?.[component.key] && (
                          <div className="border-t border-line pt-3">
                            <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-subtle">
                              What it means for you
                            </p>
                            <p className="text-[13px] leading-relaxed text-ink">
                              {data.explanations[component.key]}
                            </p>
                          </div>
                        )}
                      </CardBody>
                    </Card>
                  ))}
                </div>

                <Card className="card-pad">
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-subtle">
                    Method
                  </p>
                  <div className="scroll-x mt-2">
                    <p className="whitespace-nowrap font-mono text-[11.5px] text-muted">{data.formula}</p>
                  </div>
                  <p className="mt-3 text-[12.5px] leading-relaxed text-subtle">
                    {data.method?.note} Embeddings: {data.method?.embedding_model?.model}
                    {' '}({data.method?.embedding_model?.dimension} dimensions).
                    Vector store: {data.method?.vector_store?.name}.
                  </p>
                </Card>

                <SourceList sources={data.sources} title="Passages used for the explanations" />
              </div>
            </TabPanel>

            {/* ================================================== SKILLS */}
            <TabPanel id="skills">
              <div className="space-y-5">
                <div className="grid gap-4 sm:grid-cols-3">
                  {[
                    { key: 'matched', label: 'Present', count: skills.matched.length, tone: 'good',
                      note: 'Named in your resume AND shown in a project or role.' },
                    { key: 'partial', label: 'Partially matched', count: skills.partial.length, tone: 'warn',
                      note: 'Claimed but not demonstrated, or only a related technology appears.' },
                    { key: 'missing', label: 'Missing', count: skills.missing.length, tone: 'critical',
                      note: 'Not in your resume, and nothing semantically close either.' },
                  ].map((bucket) => (
                    <Card key={bucket.key} className="card-pad">
                      <div className="flex items-center gap-2.5">
                        <span
                          aria-hidden="true"
                          className={cx(
                            'flex h-6 w-6 items-center justify-center rounded-full text-[12px] font-bold',
                            bucket.tone === 'good' ? 'bg-good/15 text-good'
                              : bucket.tone === 'warn' ? 'bg-warn/20 text-warn'
                                : 'bg-critical/15 text-critical'
                          )}
                        >
                          {bucket.tone === 'good' ? '✓' : bucket.tone === 'warn' ? '!' : '✗'}
                        </span>
                        <span className="text-[24px] font-bold leading-none tabular-nums text-ink">
                          {bucket.count}
                        </span>
                      </div>
                      <p className="mt-2.5 text-[13px] font-semibold text-ink">{bucket.label}</p>
                      <p className="mt-1 text-[12.5px] leading-relaxed text-muted">{bucket.note}</p>
                    </Card>
                  ))}
                </div>

                {[
                  { key: 'matched', title: 'Skills you have', items: skills.matched },
                  { key: 'partial', title: 'Skills that need stronger evidence', items: skills.partial },
                  { key: 'missing', title: 'Skills you are missing', items: skills.missing },
                ].map((group) =>
                  group.items.length ? (
                    <Card key={group.key}>
                      <CardHeader title={group.title} action={<Badge>{group.items.length}</Badge>} />
                      <CardBody>
                        <ul className="divide-y divide-line">
                          {group.items.map((item) => (
                            <li key={item.skill} className="py-3 first:pt-0 last:pb-0">
                              <div className="flex flex-wrap items-center gap-2">
                                <StatusPill status={group.key}>{item.skill}</StatusPill>
                                <Badge tone={item.importance === 'required' ? 'brand' : 'neutral'}>
                                  {item.importance}
                                </Badge>
                                {item.mentions > 0 && (
                                  <span className="text-[11.5px] text-subtle">
                                    mentioned {item.mentions}×
                                  </span>
                                )}
                              </div>
                              <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{item.reason}</p>
                              {item.evidence && (
                                <details className="mt-2">
                                  <summary className="cursor-pointer text-[12px] font-medium text-subtle hover:text-brand">
                                    Show the closest passage in your resume
                                  </summary>
                                  <div className="mt-2 rounded-lg border border-line bg-raised/50 p-3">
                                    <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-subtle">
                                      {item.citation}
                                    </p>
                                    <p className="whitespace-pre-wrap text-[12.5px] leading-relaxed text-muted">
                                      {item.evidence}
                                    </p>
                                  </div>
                                </details>
                              )}
                            </li>
                          ))}
                        </ul>
                      </CardBody>
                    </Card>
                  ) : null
                )}

                {skills.extra?.length > 0 && (
                  <Card>
                    <CardHeader
                      title="Skills you have that this job didn't ask for"
                      subtitle="Not a negative — but they don't add to the match score for this particular role."
                      action={<Badge>{skills.extra.length}</Badge>}
                    />
                    <CardBody>
                      <div className="flex flex-wrap gap-1.5">
                        {skills.extra.map((skill) => (
                          <Badge key={skill}>{skill}</Badge>
                        ))}
                      </div>
                    </CardBody>
                  </Card>
                )}
              </div>
            </TabPanel>

            {/* ================================================ KEYWORDS */}
            <TabPanel id="keywords">
              <div className="space-y-5">
                <Card className="card-pad">
                  <div className="flex flex-wrap items-center justify-between gap-4">
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-wider text-subtle">
                        ATS keyword score
                      </p>
                      <p className="mt-1 text-[34px] font-bold leading-none tabular-nums text-ink">
                        {ats.score}%
                      </p>
                      <p className="mt-1.5 text-[13px] text-muted">
                        {ats.matched_count} of {ats.total} keywords found
                      </p>
                    </div>
                    <p className="max-w-md text-[12.5px] leading-relaxed text-muted">
                      {ats.calculation}
                    </p>
                  </div>
                </Card>

                <Card>
                  <CardHeader
                    title="Keyword coverage"
                    subtitle="Hover any keyword to see where it appears in your resume."
                  />
                  <CardBody>
                    <KeywordGrid keywords={ats.keywords} />
                  </CardBody>
                </Card>

                {ats.high_priority_missing?.length > 0 && (
                  <Card className="border-warn/30 bg-warn/[0.04]">
                    <CardHeader
                      title="High-importance keywords you're missing"
                      subtitle="These appear early in the posting, which usually means they matter most."
                    />
                    <CardBody>
                      <div className="flex flex-wrap gap-1.5">
                        {ats.high_priority_missing.map((keyword) => (
                          <StatusPill key={keyword} status="missing">{keyword}</StatusPill>
                        ))}
                      </div>
                      <p className="mt-4 rounded-xl bg-surface p-3.5 text-[12.5px] leading-relaxed text-muted">
                        {ats.guidance}
                      </p>
                    </CardBody>
                  </Card>
                )}
              </div>
            </TabPanel>

            {/* ================================================ PROJECTS */}
            <TabPanel id="projects">
              {data.projects?.length ? (
                <div className="space-y-5">
                  <Card>
                    <CardHeader
                      title="Ranked by relevance to this job"
                      icon={
                        <InfoTip text="Each project is embedded as a vector, then compared with cosine similarity against every responsibility and required skill in the posting. The score is the mean similarity to its closest requirements, rescaled to 0-100." />
                      }
                      subtitle="Computed with embeddings — hover a bar to see the arithmetic."
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

                  {projects.loading && !projects.data && (
                    <p className="text-[13px] text-muted">Generating explanations...</p>
                  )}

                  {(projects.data?.projects || data.projects).map((project, index) => (
                    <Card key={project.name}>
                      <CardHeader
                        title={`${index + 1}. ${project.name}`}
                        action={
                          <span className="text-[20px] font-bold tabular-nums text-ink">
                            {project.relevance}%
                          </span>
                        }
                        subtitle={project.description}
                      />
                      <CardBody className="space-y-4">
                        {project.why_relevant && (
                          <div>
                            <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-subtle">
                              Why it scored this way
                            </p>
                            <p className="text-[13.5px] leading-relaxed text-ink">
                              {project.why_relevant}
                            </p>
                          </div>
                        )}

                        {project.matching_technologies?.length > 0 && (
                          <div>
                            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-subtle">
                              Technologies this job also asks for
                            </p>
                            <div className="flex flex-wrap gap-1.5">
                              {project.matching_technologies.map((tech) => (
                                <StatusPill key={tech} status="matched">{tech}</StatusPill>
                              ))}
                            </div>
                          </div>
                        )}

                        {project.top_requirements?.length > 0 && (
                          <div>
                            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-subtle">
                              Closest job requirements
                            </p>
                            <ul className="space-y-1.5">
                              {project.top_requirements.map((requirement, position) => (
                                <li
                                  key={position}
                                  className="flex items-start justify-between gap-3 text-[12.5px] leading-relaxed"
                                >
                                  <span className="text-muted">{requirement.requirement}</span>
                                  <span className="shrink-0 tabular-nums text-subtle">
                                    {(requirement.similarity * 100).toFixed(0)}%
                                  </span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {project.what_to_emphasize && (
                          <div className="rounded-xl border border-brand/25 bg-brand/[0.05] p-3.5">
                            <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-brand">
                              What to emphasise for this role
                            </p>
                            <p className="text-[13px] leading-relaxed text-ink">
                              {project.what_to_emphasize}
                            </p>
                          </div>
                        )}
                      </CardBody>
                    </Card>
                  ))}

                  <SourceList sources={projects.data?.sources} title="Passages used" />
                </div>
              ) : (
                <Card className="card-pad">
                  <p className="text-[13.5px] leading-relaxed text-muted">
                    No projects were found in your resume, so there is nothing to rank. Adding two or
                    three projects with the technologies you used is the single highest-impact change
                    a student resume can make.
                  </p>
                </Card>
              )}
            </TabPanel>

            {/* ================================================= ACTIONS */}
            <TabPanel id="actions">
              {priorities.error ? (
                <Card className="card-pad">
                  <p className="text-[13.5px] text-muted">{priorities.error.message}</p>
                </Card>
              ) : priorities.loading && !priorities.data ? (
                <p className="text-[13px] text-muted">Building your action plan...</p>
              ) : priorities.data ? (
                <div className="space-y-5">
                  {[
                    { key: 'high', title: 'High priority', tone: 'critical',
                      note: 'A required skill or a required piece of evidence is missing or invisible.' },
                    { key: 'medium', title: 'Medium priority', tone: 'warn',
                      note: 'Something real is there, but it is under-sold.' },
                    { key: 'low', title: 'Low priority', tone: 'neutral',
                      note: 'Polish: wording, ordering, consistency.' },
                    { key: 'already_strong', title: 'Already strong', tone: 'good',
                      note: 'Working well — keep it exactly as it is.' },
                  ].map((bucket) => {
                    const items = priorities.data[bucket.key] || []
                    if (!items.length) return null
                    return (
                      <Card key={bucket.key}>
                        <CardHeader
                          title={bucket.title}
                          subtitle={bucket.note}
                          action={<Badge tone={bucket.tone}>{items.length}</Badge>}
                        />
                        <CardBody>
                          <ul className="space-y-4">
                            {items.map((item, index) => (
                              <li key={index} className="flex gap-3">
                                <span
                                  aria-hidden="true"
                                  className={cx(
                                    'mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold',
                                    bucket.tone === 'critical' ? 'bg-critical/15 text-critical'
                                      : bucket.tone === 'warn' ? 'bg-warn/20 text-warn'
                                        : bucket.tone === 'good' ? 'bg-good/15 text-good'
                                          : 'bg-raised text-subtle'
                                  )}
                                >
                                  {bucket.tone === 'good' ? '✓' : index + 1}
                                </span>
                                <div className="min-w-0">
                                  <p className="flex flex-wrap items-center gap-2 text-[13.5px] font-semibold text-ink">
                                    {item.title}
                                    <Badge>{item.effort}</Badge>
                                  </p>
                                  <p className="mt-1 text-[13px] leading-relaxed text-muted">{item.detail}</p>
                                  {item.why && (
                                    <p className="mt-1.5 text-[12.5px] leading-relaxed text-subtle">
                                      Why: {item.why}
                                    </p>
                                  )}
                                </div>
                              </li>
                            ))}
                          </ul>
                        </CardBody>
                      </Card>
                    )
                  })}
                  <SourceList sources={priorities.data.sources} title="Passages used" />
                </div>
              ) : null}
            </TabPanel>
          </Tabs>
        )}
      </PageState>
    </div>
  )
}
