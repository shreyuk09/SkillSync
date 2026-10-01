import * as api from '../services/api'
import { useAnalysis } from '../hooks/useAnalysis'
import { PageHeader, PageState, RefreshingBar } from '../components/PageState'
import { Badge, Button, Card, CardBody, CardHeader } from '../components/ui'

function List({ items, marker = '·' }) {
  if (!items?.length) {
    return <p className="text-[13px] italic text-subtle">Not stated in this job description.</p>
  }
  return (
    <ul className="space-y-2">
      {items.map((item, index) => (
        <li key={index} className="flex gap-2.5 text-[13.5px] leading-relaxed text-muted">
          <span aria-hidden="true" className="mt-0.5 shrink-0 text-brand">{marker}</span>
          {item}
        </li>
      ))}
    </ul>
  )
}

export default function JobPage() {
  const { data, loading, error, run, refresh } = useAnalysis(api.getJobProfile)

  return (
    <div className="space-y-6">
      <PageHeader
        title="Job description"
        subtitle="The requirements extracted from the posting. This is what your resume is being compared against."
        action={
          data && (
            <Button size="sm" variant="secondary" onClick={refresh} loading={loading}>
              Re-parse
            </Button>
          )
        }
      />

      <RefreshingBar show={loading && Boolean(data)} label="Re-parsing the job description..." />

      <PageState needs="jd" loading={loading} error={error} onRetry={() => run(false)} data={data}>
        {data && (
          <div className="space-y-5">
            {/* ------------------------------------------------- role card */}
            <Card className="card-pad">
              <h2 className="text-[22px] font-bold tracking-tight text-ink">
                {data.job_title || 'Job title not found'}
              </h2>
              <div className="mt-2.5 flex flex-wrap gap-1.5">
                {data.company && <Badge tone="brand">{data.company}</Badge>}
                {data.location && <Badge>{data.location}</Badge>}
                {data.employment_type && <Badge>{data.employment_type}</Badge>}
                {data.seniority && <Badge>{data.seniority} level</Badge>}
              </div>
              {data.summary && (
                <p className="mt-4 text-[14px] leading-relaxed text-muted">{data.summary}</p>
              )}

              <dl className="mt-5 grid grid-cols-2 gap-4 border-t border-line pt-4 sm:grid-cols-4">
                {[
                  { label: 'Required skills', value: data.stats?.required_skill_count ?? 0 },
                  { label: 'Preferred skills', value: data.stats?.preferred_skill_count ?? 0 },
                  { label: 'Responsibilities', value: data.stats?.responsibility_count ?? 0 },
                  {
                    label: 'Min. experience',
                    value: data.min_experience_years ? `${data.min_experience_years} yr` : 'None',
                  },
                ].map((stat) => (
                  <div key={stat.label}>
                    <dd className="text-[20px] font-bold leading-none tabular-nums text-ink">
                      {stat.value}
                    </dd>
                    <dt className="mt-1.5 text-[11px] uppercase tracking-wider text-subtle">
                      {stat.label}
                    </dt>
                  </div>
                ))}
              </dl>
            </Card>

            {/* ------------------------------------------------------ skills */}
            <div className="grid gap-5 lg:grid-cols-2">
              <Card>
                <CardHeader
                  title="Required skills"
                  subtitle="Must-haves. These carry full weight in the match score."
                  action={<Badge tone="brand">{data.required_skills?.length ?? 0}</Badge>}
                />
                <CardBody>
                  {data.required_skills?.length ? (
                    <div className="flex flex-wrap gap-1.5">
                      {data.required_skills.map((skill) => (
                        <Badge key={skill} tone="brand">{skill}</Badge>
                      ))}
                    </div>
                  ) : (
                    <p className="text-[13px] italic text-subtle">
                      This posting doesn't clearly separate required skills.
                    </p>
                  )}
                </CardBody>
              </Card>

              <Card>
                <CardHeader
                  title="Preferred skills"
                  subtitle="Nice-to-haves. Weighted at 40% of a required skill."
                  action={<Badge>{data.preferred_skills?.length ?? 0}</Badge>}
                />
                <CardBody>
                  {data.preferred_skills?.length ? (
                    <div className="flex flex-wrap gap-1.5">
                      {data.preferred_skills.map((skill) => (
                        <Badge key={skill}>{skill}</Badge>
                      ))}
                    </div>
                  ) : (
                    <p className="text-[13px] italic text-subtle">No preferred skills were listed.</p>
                  )}
                </CardBody>
              </Card>
            </div>

            {/* --------------------------------------------- responsibilities */}
            <Card>
              <CardHeader
                title="Responsibilities"
                subtitle="What the role involves day to day. These are compared semantically against your experience."
                action={<Badge>{data.responsibilities?.length ?? 0}</Badge>}
              />
              <CardBody>
                <List items={data.responsibilities} />
              </CardBody>
            </Card>

            <div className="grid gap-5 lg:grid-cols-2">
              <Card>
                <CardHeader title="Experience requirements" />
                <CardBody>
                  <p className="text-[13.5px] leading-relaxed text-muted">
                    {data.experience_note || (
                      <span className="italic text-subtle">
                        This posting doesn't state an experience requirement.
                      </span>
                    )}
                  </p>
                </CardBody>
              </Card>

              <Card>
                <CardHeader title="Education requirements" />
                <CardBody>
                  <List items={data.education_requirements} />
                </CardBody>
              </Card>
            </div>

            <div className="grid gap-5 lg:grid-cols-2">
              <Card>
                <CardHeader
                  title="Tools and technologies"
                  action={<Badge>{data.tools_and_technologies?.length ?? 0}</Badge>}
                />
                <CardBody>
                  {data.tools_and_technologies?.length ? (
                    <div className="flex flex-wrap gap-1.5">
                      {data.tools_and_technologies.map((tool) => (
                        <Badge key={tool}>{tool}</Badge>
                      ))}
                    </div>
                  ) : (
                    <p className="text-[13px] italic text-subtle">None named specifically.</p>
                  )}
                </CardBody>
              </Card>

              <Card>
                <CardHeader
                  title="ATS keywords"
                  subtitle="Ordered by how prominently the posting features them."
                  action={<Badge>{data.keywords?.length ?? 0}</Badge>}
                />
                <CardBody>
                  <ol className="flex flex-wrap gap-1.5">
                    {(data.keywords || []).map((keyword, index) => (
                      <li key={keyword}>
                        <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-raised px-2.5 py-1 text-[12px] font-medium text-muted">
                          <span className="font-mono text-[10px] text-subtle">{index + 1}</span>
                          {keyword}
                        </span>
                      </li>
                    ))}
                  </ol>
                </CardBody>
              </Card>
            </div>

            {data.soft_skills?.length > 0 && (
              <Card>
                <CardHeader title="Soft skills the posting asks for" />
                <CardBody>
                  <div className="flex flex-wrap gap-1.5">
                    {data.soft_skills.map((skill) => (
                      <Badge key={skill}>{skill}</Badge>
                    ))}
                  </div>
                </CardBody>
              </Card>
            )}
          </div>
        )}
      </PageState>
    </div>
  )
}
