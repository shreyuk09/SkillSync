import * as api from '../services/api'
import { useAnalysis } from '../hooks/useAnalysis'
import { PageHeader, PageState, RefreshingBar } from '../components/PageState'
import { Badge, Button, Card, CardBody, CardHeader, Progress } from '../components/ui'

function Section({ title, count, children, empty }) {
  return (
    <Card>
      <CardHeader
        title={title}
        action={count !== undefined && <Badge>{count}</Badge>}
      />
      <CardBody>
        {count === 0 ? (
          <p className="text-[13px] italic leading-relaxed text-subtle">{empty}</p>
        ) : (
          children
        )}
      </CardBody>
    </Card>
  )
}

export default function ResumePage() {
  const { data, loading, error, run, refresh } = useAnalysis(api.getResumeProfile)

  return (
    <div className="space-y-6">
      <PageHeader
        title="Your resume"
        subtitle="Everything below was extracted from the file you uploaded. Nothing here was inferred or filled in."
        action={
          data && (
            <Button size="sm" variant="secondary" onClick={refresh} loading={loading}>
              Re-parse
            </Button>
          )
        }
      />

      <RefreshingBar show={loading && Boolean(data)} label="Re-parsing your resume..." />

      <PageState needs="resume" loading={loading} error={error} onRetry={() => run(false)} data={data}>
        {data && (
          <div className="space-y-5">
            {/* -------------------------------------------------- identity */}
            <Card className="card-pad">
              <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <h2 className="text-[22px] font-bold tracking-tight text-ink">
                    {data.name || 'Name not found'}
                  </h2>
                  <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[13px] text-muted">
                    {data.email && <span>{data.email}</span>}
                    {data.phone && <span>{data.phone}</span>}
                    {data.location && <span>{data.location}</span>}
                  </div>
                  {data.links?.length > 0 && (
                    <div className="mt-2.5 flex flex-wrap gap-1.5">
                      {data.links.map((link) => (
                        <span
                          key={link.url}
                          className="rounded-md bg-raised px-2 py-1 text-[11.5px] font-medium text-muted"
                        >
                          {link.label || link.url}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div className="shrink-0 sm:w-52">
                  <div className="flex items-baseline justify-between">
                    <span className="text-[11.5px] font-semibold uppercase tracking-wider text-subtle">
                      Completeness
                    </span>
                    <span className="text-[15px] font-bold tabular-nums text-ink">
                      {data.completeness?.score ?? 0}%
                    </span>
                  </div>
                  <Progress className="mt-2" value={data.completeness?.score ?? 0} />
                  {data.completeness?.missing?.length > 0 && (
                    <p className="mt-2 text-[12px] leading-relaxed text-subtle">
                      Missing: {data.completeness.missing.join(', ')}
                    </p>
                  )}
                </div>
              </div>

              {data.summary && (
                <div className="mt-5 border-t border-line pt-4">
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-subtle">
                    Summary / objective
                  </p>
                  <p className="mt-1.5 text-[13.5px] leading-relaxed text-muted">{data.summary}</p>
                </div>
              )}
            </Card>

            {/* ------------------------------------------------ doc stats */}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                { label: 'Pages', value: data.stats?.page_count ?? 0 },
                { label: 'Words', value: (data.stats?.word_count ?? 0).toLocaleString() },
                { label: 'Sections found', value: data.stats?.sections_found?.length ?? 0 },
                { label: 'Chunks indexed', value: data.document?.chunks ?? 0 },
              ].map((stat) => (
                <div key={stat.label} className="card px-4 py-3.5">
                  <p className="text-[20px] font-bold leading-none tabular-nums text-ink">{stat.value}</p>
                  <p className="mt-1.5 text-[11px] uppercase tracking-wider text-subtle">{stat.label}</p>
                </div>
              ))}
            </div>

            <div className="grid gap-5 lg:grid-cols-2">
              {/* ------------------------------------------------ education */}
              <Section
                title="Education"
                count={data.education?.length ?? 0}
                empty="No education section was found in your resume."
              >
                <ul className="space-y-4">
                  {(data.education || []).map((entry, index) => (
                    <li key={index} className="border-l-2 border-brand/30 pl-3.5">
                      <p className="text-[14px] font-semibold text-ink">
                        {entry.degree}
                        {entry.field ? ` in ${entry.field}` : ''}
                      </p>
                      <p className="mt-0.5 text-[13px] text-muted">{entry.institution}</p>
                      <div className="mt-1.5 flex flex-wrap items-center gap-2">
                        {entry.dates && <Badge>{entry.dates}</Badge>}
                        {entry.score && (
                          <Badge tone="brand">
                            {entry.score_type || 'Score'}: {entry.score}
                          </Badge>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </Section>

              {/* --------------------------------------------------- skills */}
              <Section title="Skills" count={(data.technical_skills?.length ?? 0) + (data.soft_skills?.length ?? 0)}
                empty="No skills section was found in your resume.">
                <div className="space-y-4">
                  <div>
                    <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-subtle">
                      Technical · {data.technical_skills?.length ?? 0}
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {(data.technical_skills || []).map((skill) => (
                        <Badge key={skill} tone="brand">{skill}</Badge>
                      ))}
                    </div>
                  </div>
                  {data.soft_skills?.length > 0 && (
                    <div>
                      <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-subtle">
                        Soft · {data.soft_skills.length}
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {data.soft_skills.map((skill) => (
                          <Badge key={skill}>{skill}</Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </Section>
            </div>

            {/* -------------------------------------------------- projects */}
            <Section
              title="Projects"
              count={data.projects?.length ?? 0}
              empty="No projects section was found in your resume."
            >
              <div className="grid gap-4 sm:grid-cols-2">
                {(data.projects || []).map((project, index) => (
                  <div key={index} className="rounded-xl border border-line p-4">
                    <div className="flex items-start justify-between gap-3">
                      <h4 className="text-[14px] font-semibold text-ink">{project.name}</h4>
                      {project.dates && <span className="shrink-0 text-[11.5px] text-subtle">{project.dates}</span>}
                    </div>
                    {project.description && (
                      <p className="mt-2 text-[13px] leading-relaxed text-muted">{project.description}</p>
                    )}
                    {project.highlights?.length > 0 && (
                      <ul className="mt-2.5 space-y-1">
                        {project.highlights.map((highlight, position) => (
                          <li key={position} className="flex gap-2 text-[12.5px] leading-relaxed text-muted">
                            <span aria-hidden="true" className="text-subtle">·</span>
                            {highlight}
                          </li>
                        ))}
                      </ul>
                    )}
                    {project.technologies?.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {project.technologies.map((tech) => (
                          <span
                            key={tech}
                            className="rounded-md bg-raised px-2 py-0.5 text-[11px] font-medium text-muted"
                          >
                            {tech}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Section>

            {/* ---------------------------------------- experience + interns */}
            {['experience', 'internships'].map((key) => {
              const items = data[key] || []
              if (!items.length) return null
              return (
                <Section
                  key={key}
                  title={key === 'experience' ? 'Work experience' : 'Internships'}
                  count={items.length}
                >
                  <ul className="space-y-5">
                    {items.map((role, index) => (
                      <li key={index} className="border-l-2 border-brand/30 pl-3.5">
                        <div className="flex flex-wrap items-baseline justify-between gap-2">
                          <p className="text-[14px] font-semibold text-ink">{role.title}</p>
                          {role.dates && <span className="text-[11.5px] text-subtle">{role.dates}</span>}
                        </div>
                        <p className="mt-0.5 text-[13px] text-muted">
                          {role.organization}
                          {role.location ? ` · ${role.location}` : ''}
                        </p>
                        {role.highlights?.length > 0 && (
                          <ul className="mt-2 space-y-1">
                            {role.highlights.map((highlight, position) => (
                              <li key={position} className="flex gap-2 text-[12.5px] leading-relaxed text-muted">
                                <span aria-hidden="true" className="text-subtle">·</span>
                                {highlight}
                              </li>
                            ))}
                          </ul>
                        )}
                        {role.technologies?.length > 0 && (
                          <div className="mt-2.5 flex flex-wrap gap-1.5">
                            {role.technologies.map((tech) => (
                              <span
                                key={tech}
                                className="rounded-md bg-raised px-2 py-0.5 text-[11px] font-medium text-muted"
                              >
                                {tech}
                              </span>
                            ))}
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                </Section>
              )
            })}

            {/* ------------------------------- certifications / achievements */}
            <div className="grid gap-5 lg:grid-cols-2">
              <Section
                title="Certifications"
                count={data.certifications?.length ?? 0}
                empty="No certifications were listed in your resume."
              >
                <ul className="space-y-2.5">
                  {(data.certifications || []).map((item, index) => (
                    <li key={index} className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-[13.5px] font-medium text-ink">{item.name}</p>
                        {item.issuer && <p className="text-[12.5px] text-muted">{item.issuer}</p>}
                      </div>
                      {item.date && <span className="shrink-0 text-[11.5px] text-subtle">{item.date}</span>}
                    </li>
                  ))}
                </ul>
              </Section>

              <Section
                title="Achievements"
                count={data.achievements?.length ?? 0}
                empty="No achievements section was found in your resume."
              >
                <ul className="space-y-2">
                  {(data.achievements || []).map((item, index) => (
                    <li key={index} className="flex gap-2.5 text-[13px] leading-relaxed text-muted">
                      <span aria-hidden="true" className="text-brand">★</span>
                      {item}
                    </li>
                  ))}
                </ul>
              </Section>
            </div>

            {data.publications?.length > 0 && (
              <Section title="Publications" count={data.publications.length}>
                <ul className="space-y-2">
                  {data.publications.map((item, index) => (
                    <li key={index} className="text-[13px] leading-relaxed text-muted">{item}</li>
                  ))}
                </ul>
              </Section>
            )}

            {/* --------------------------------------- what wasn't found */}
            {data.missing_fields?.length > 0 && (
              <Card className="border-warn/30 bg-warn/[0.05] card-pad">
                <p className="text-[13.5px] font-semibold text-ink">
                  <span aria-hidden="true" className="mr-1.5 text-warn">!</span>
                  Fields we couldn't find in your resume
                </p>
                <p className="mt-1.5 text-[13px] leading-relaxed text-muted">
                  {data.missing_fields.join(', ')}. These are left blank rather than guessed —
                  add them to your resume if they apply to you.
                </p>
              </Card>
            )}
          </div>
        )}
      </PageState>
    </div>
  )
}
