import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext'
import * as api from '../services/api'
import { Dropzone, PasteBox } from '../components/Dropzone'
import { PipelineTrace } from '../components/PipelineTrace'
import { Badge, Button, Card, CardBody, CardHeader, Modal, Tab, TabList, TabPanel, Tabs, cx } from '../components/ui'

export default function Upload() {
  const navigate = useNavigate()
  const {
    sessionId, ensureSession, refreshStatus, documentsChanged, status,
    toast, toastError, ready,
  } = useApp()

  const [samples, setSamples] = useState([])
  const [busy, setBusy] = useState('')
  const [traces, setTraces] = useState({})
  const [jdMode, setJdMode] = useState('upload')
  // What the user is about to replace, if anything: 'resume' | 'jd' | 'sample-jd'.
  const [pendingSwap, setPendingSwap] = useState('')
  const [sampleChooserOpen, setSampleChooserOpen] = useState(false)
  const resumePicker = useRef(null)
  const jdPicker = useRef(null)

  useEffect(() => {
    api.getSamples().then(setSamples).catch(() => {})
    ensureSession().catch(toastError)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const afterIngest = async (docType, result) => {
    setTraces((current) => ({ ...current, [docType]: result }))
    // The server discards this session's cached analysis whenever a document
    // is ingested; this makes every mounted page drop its copy to match.
    const next = await documentsChanged()
    toast(
      `${docType === 'resume' ? 'Resume' : 'Job description'} indexed — ${result.chunk_count} chunks embedded.`,
      { type: 'success' }
    )
    if (next?.ready) {
      toast('Both documents are in. Opening your dashboard...', { type: 'info', duration: 2500 })
      setTimeout(() => navigate('/dashboard'), 900)
    }
  }

  const upload = async (docType, file) => {
    setBusy(docType)
    try {
      const id = await ensureSession()
      const result = await api.uploadDocument(id, docType, file)
      await afterIngest(docType, result)
    } catch (error) {
      toastError(error)
    } finally {
      setBusy('')
    }
  }

  const paste = async (docType, text) => {
    setBusy(docType)
    try {
      const id = await ensureSession()
      const result = await api.pasteDocument(id, docType, text, null)
      await afterIngest(docType, result)
    } catch (error) {
      toastError(error)
    } finally {
      setBusy('')
    }
  }

  const loadSample = async (sample) => {
    setBusy(sample.doc_type)
    try {
      const id = await ensureSession()
      const payload =
        sample.doc_type === 'resume' ? { resumeId: sample.id } : { jdId: sample.id }
      const result = await api.loadSamples(id, payload)
      const loaded = result.loaded[0]
      await afterIngest(sample.doc_type, {
        ...loaded,
        chunk_count: loaded.chunk_count,
        pipeline: loaded.pipeline,
      })
    } catch (error) {
      toastError(error)
    } finally {
      setBusy('')
    }
  }

  /**
   * Swapping a document throws the current analysis away, so ask first.
   *
   * Confirmation only matters once an analysis could exist; before that there
   * is nothing to lose and the extra click would be noise.
   */
  const requestSwap = (kind) => {
    if (ready) return setPendingSwap(kind)
    return startSwap(kind)
  }

  const startSwap = (kind) => {
    setPendingSwap('')
    if (kind === 'sample-jd') return setSampleChooserOpen(true)
    const picker = kind === 'resume' ? resumePicker : jdPicker
    picker.current?.click()
  }

  const onPicked = (docType) => (event) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (file) upload(docType, file)
  }

  const loadFullDemo = async () => {
    setBusy('demo')
    try {
      const id = await ensureSession()
      await api.loadSamples(id, { resumeId: 'sample_resume', jdId: 'jd_software_developer' })
      await refreshStatus()
      toast('Sample resume and job description loaded.', { type: 'success' })
      navigate('/dashboard')
    } catch (error) {
      toastError(error)
    } finally {
      setBusy('')
    }
  }

  const resumeDoc = status?.documents?.find((doc) => doc.doc_type === 'resume')
  const jdDoc = status?.documents?.find((doc) => doc.doc_type === 'jd')
  const sampleJds = samples.filter((sample) => sample.doc_type === 'jd')

  const SWAP_COPY = {
    resume: 'a new resume',
    jd: 'a new job description',
    'sample-jd': 'a sample job description',
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      {/* Hidden pickers, opened by the buttons on each card. */}
      <input
        ref={resumePicker}
        type="file"
        accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg,.webp,.heic,.tiff"
        className="hidden"
        onChange={onPicked('resume')}
      />
      <input
        ref={jdPicker}
        type="file"
        accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg,.webp,.heic,.tiff"
        className="hidden"
        onChange={onPicked('jd')}
      />

      <Modal
        open={Boolean(pendingSwap)}
        onClose={() => setPendingSwap('')}
        title="This will clear your current analysis. Continue?"
        width="max-w-md"
      >
        {/* The Modal subtitle is a single truncated line, so the explanation
            goes in the body where it can wrap. */}
        <p className="mb-4 text-[13px] leading-relaxed text-muted">
          Loading {SWAP_COPY[pendingSwap] ?? 'a new document'} replaces the one you have now.
          Your existing results are discarded and a fresh analysis runs on the new pair.
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setPendingSwap('')}>
            Cancel
          </Button>
          <Button onClick={() => startSwap(pendingSwap)}>Continue</Button>
        </div>
      </Modal>

      <Modal
        open={sampleChooserOpen}
        onClose={() => setSampleChooserOpen(false)}
        title="Choose a sample job description"
      >
        <p className="mb-4 text-[13px] leading-relaxed text-muted">
          The chosen sample replaces your current job description, and a fresh analysis runs
          on it with your existing resume.
        </p>
        <ul className="space-y-2">
          {sampleJds.map((sample) => (
            <li key={sample.id}>
              <button
                onClick={() => {
                  setSampleChooserOpen(false)
                  loadSample(sample)
                }}
                disabled={Boolean(busy)}
                className="w-full rounded-xl border border-line p-3.5 text-left transition-all hover:border-brand/50 hover:bg-raised/60 disabled:opacity-50"
              >
                <p className="text-[13.5px] font-semibold text-ink">{sample.label}</p>
                <p className="mt-1 text-[12.5px] leading-relaxed text-muted">
                  {sample.description}
                </p>
              </button>
            </li>
          ))}
        </ul>
      </Modal>

      <header>
        <h1 className="text-[24px] font-bold tracking-tight text-ink">Your documents</h1>
        <p className="mt-1.5 text-[14px] leading-relaxed text-muted">
          Both are needed before the analysis can run. Everything is processed in memory —
          the file itself is never written to disk.
        </p>
      </header>

      {/* -------------------------------------------------- quick demo bar */}
      {!ready && (
        <Card className="border-brand/25 bg-brand/[0.05] card-pad">
          <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
            <div>
              <p className="text-[14px] font-semibold text-ink">Just want to see it work?</p>
              <p className="mt-1 text-[13px] leading-relaxed text-muted">
                Load a realistic sample resume and a backend developer job description in one click.
              </p>
            </div>
            <Button onClick={loadFullDemo} loading={busy === 'demo'} className="shrink-0">
              Load the demo
            </Button>
          </div>
        </Card>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        {/* ------------------------------------------------------- resume */}
        <Card>
          <CardHeader
            title="Resume"
            subtitle="PDF, DOCX, TXT or MD"
            action={
              resumeDoc ? (
                <Badge tone="good" icon={<span aria-hidden="true">✓</span>}>Indexed</Badge>
              ) : (
                <Badge>Required</Badge>
              )
            }
          />
          <CardBody>
            {resumeDoc ? (
              <DocumentSummary
                doc={resumeDoc}
                trace={traces.resume}
                onReplace={() => setTraces((c) => ({ ...c, resume: null }))}
                onView={() => navigate('/resume')}
                extraActions={
                  <Button
                    size="sm"
                    variant="secondary"
                    loading={busy === 'resume'}
                    onClick={() => requestSwap('resume')}
                  >
                    Upload new resume
                  </Button>
                }
                replaceSlot={
                  <Dropzone
                    compact
                    label="Replace resume"
                    hint="Uploading again re-runs the whole pipeline"
                    loading={busy === 'resume'}
                    onFile={(file) => upload('resume', file)}
                  />
                }
              />
            ) : (
              <>
                <Dropzone
                  label="Upload your resume"
                  loading={busy === 'resume'}
                  onFile={(file) => upload('resume', file)}
                />
                {samples.some((s) => s.doc_type === 'resume') && (
                  <button
                    onClick={() => loadSample(samples.find((s) => s.doc_type === 'resume'))}
                    className="mt-3 text-[12.5px] font-medium text-brand underline-offset-2 hover:underline"
                  >
                    or use the sample resume
                  </button>
                )}
              </>
            )}
          </CardBody>
        </Card>

        {/* ---------------------------------------------------------- JD */}
        <Card>
          <CardHeader
            title="Job description"
            subtitle="Upload a file or paste the posting"
            action={
              jdDoc ? (
                <Badge tone="good" icon={<span aria-hidden="true">✓</span>}>Indexed</Badge>
              ) : (
                <Badge>Required</Badge>
              )
            }
          />
          <CardBody>
            {jdDoc ? (
              <DocumentSummary
                doc={jdDoc}
                trace={traces.jd}
                onView={() => navigate('/job')}
                extraActions={
                  <>
                    <Button
                      size="sm"
                      variant="secondary"
                      loading={busy === 'jd'}
                      onClick={() => requestSwap('jd')}
                    >
                      Upload new JD
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={!sampleJds.length}
                      onClick={() => requestSwap('sample-jd')}
                    >
                      Use sample JD
                    </Button>
                  </>
                }
                replaceSlot={
                  <Dropzone
                    compact
                    label="Replace job description"
                    hint="Uploading again re-runs the whole pipeline"
                    loading={busy === 'jd'}
                    onFile={(file) => upload('jd', file)}
                  />
                }
              />
            ) : (
              <Tabs value={jdMode} onChange={setJdMode}>
                <TabList>
                  <Tab id="upload">Upload a file</Tab>
                  <Tab id="paste">Paste text</Tab>
                  <Tab id="sample">Samples</Tab>
                </TabList>

                <TabPanel id="upload">
                  <Dropzone
                    label="Upload the job description"
                    loading={busy === 'jd'}
                    onFile={(file) => upload('jd', file)}
                  />
                </TabPanel>

                <TabPanel id="paste">
                  <PasteBox
                    loading={busy === 'jd'}
                    onSubmit={(text) => paste('jd', text)}
                    placeholder={
                      'Paste the full job posting here — responsibilities, required skills, qualifications...'
                    }
                  />
                </TabPanel>

                <TabPanel id="sample">
                  <ul className="space-y-2">
                    {sampleJds.map((sample) => (
                      <li key={sample.id}>
                        <button
                          onClick={() => loadSample(sample)}
                          disabled={Boolean(busy)}
                          className="w-full rounded-xl border border-line p-3.5 text-left transition-all hover:border-brand/50 hover:bg-raised/60 disabled:opacity-50"
                        >
                          <p className="text-[13.5px] font-semibold text-ink">{sample.label}</p>
                          <p className="mt-1 text-[12.5px] leading-relaxed text-muted">
                            {sample.description}
                          </p>
                        </button>
                      </li>
                    ))}
                  </ul>
                </TabPanel>
              </Tabs>
            )}
          </CardBody>
        </Card>
      </div>

      {/* ------------------------------------------------- pipeline traces */}
      {(traces.resume || traces.jd) && (
        <Card>
          <CardHeader
            title="What the RAG pipeline just did"
            subtitle="Each stage ran on the server, in this order, on the document you uploaded."
          />
          <CardBody>
            <div className="grid gap-8 sm:grid-cols-2">
              {['resume', 'jd'].map((docType) =>
                traces[docType] ? (
                  <div key={docType}>
                    <p className="mb-3 text-[12px] font-semibold uppercase tracking-wider text-subtle">
                      {docType === 'resume' ? 'Resume' : 'Job description'}
                      {traces[docType].elapsed_ms !== undefined && (
                        <span className="ml-2 font-normal normal-case tracking-normal text-subtle">
                          {traces[docType].elapsed_ms} ms
                        </span>
                      )}
                    </p>
                    <PipelineTrace stages={traces[docType].pipeline} />
                  </div>
                ) : null
              )}
            </div>
          </CardBody>
        </Card>
      )}

      {ready && (
        <div className="flex justify-end">
          <Button size="lg" onClick={() => navigate('/dashboard')}>
            Go to dashboard
            <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 10h12M11 5l5 5-5 5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </Button>
        </div>
      )}
    </div>
  )
}

function DocumentSummary({ doc, trace, onView, replaceSlot, extraActions }) {
  const [replacing, setReplacing] = useState(false)

  return (
    <div>
      <div className="rounded-xl border border-line bg-raised/50 p-4">
        <p className="truncate text-[14px] font-semibold text-ink">{doc.name}</p>
        <dl className="mt-3 grid grid-cols-3 gap-3 text-center">
          {[
            { label: 'Pages', value: doc.pages },
            { label: 'Chunks', value: doc.chunks },
            { label: 'Sections', value: doc.sections?.length ?? 0 },
          ].map((stat) => (
            <div key={stat.label}>
              <dd className="text-[19px] font-bold leading-none tabular-nums text-ink">{stat.value}</dd>
              <dt className="mt-1 text-[11px] uppercase tracking-wider text-subtle">{stat.label}</dt>
            </div>
          ))}
        </dl>
        {doc.sections?.length > 0 && (
          <div className="mt-3.5 flex flex-wrap gap-1.5">
            {doc.sections.map((section) => (
              <span
                key={section}
                className="rounded-md bg-surface px-2 py-1 text-[11px] font-medium text-muted ring-1 ring-inset ring-line"
              >
                {section}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm" variant="secondary" onClick={onView}>
          View extracted data
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setReplacing((v) => !v)}>
          {replacing ? 'Cancel' : 'Replace'}
        </Button>
        {extraActions}
      </div>

      {replacing && <div className="mt-3">{replaceSlot}</div>}
    </div>
  )
}
