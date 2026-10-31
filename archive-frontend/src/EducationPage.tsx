import { BadgeCheck, BookOpen, Clock3, FlaskConical, HeartPulse, Lightbulb, LockKeyhole, Pill, Scale, ShieldCheck } from 'lucide-react'
import { useState } from 'react'

const sources = {
  who: 'https://www.who.int/news-room/fact-sheets/detail/hiv-aids',
  testing: 'https://www.cdc.gov/hiv/testing/',
  prevention: 'https://www.cdc.gov/hiv/prevention/',
  prep: 'https://www.cdc.gov/hiv/prevention/prep.html',
  pep: 'https://www.cdc.gov/hiv/prevention/pep.html',
  treatment: 'https://www.cdc.gov/hiv/treatment/index.html',
  law: 'https://lawphil.net/statutes/repacts/ra2018/ra_11166_2018.html',
  language: 'https://www.unaids.org/en/resources/documents/2024/terminology_guidelines',
  facilities: 'https://pnac.gov.ph/department-of-health-department-circular-no-2026-0220/',
}

const Link = ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href} target="_blank" rel="noreferrer">{children}<span aria-hidden="true"> ↗</span></a>

export default function EducationPage({ onFindCare }: { onFindCare: () => void }) {
  const [activeTopic, setActiveTopic] = useState(0)
  const topics = [
    ['HIV basics', BookOpen, 'https://images.pexels.com/photos/4421496/pexels-photo-4421496.jpeg?auto=compress&cs=tinysrgb&w=1200', 'Friends sharing an open, supportive conversation'],
    ['Testing', FlaskConical, 'https://images.pexels.com/photos/5327585/pexels-photo-5327585.jpeg?auto=compress&cs=tinysrgb&w=1200', 'Healthcare professional speaking privately with a patient'],
    ['Prevention', ShieldCheck, 'https://images.pexels.com/photos/3845983/pexels-photo-3845983.jpeg?auto=compress&cs=tinysrgb&w=1200', 'Healthcare worker providing supportive care'],
    ['PrEP & PEP', Pill, 'https://images.pexels.com/photos/5327585/pexels-photo-5327585.jpeg?auto=compress&cs=tinysrgb&w=1200', 'Healthcare professional discussing prevention medication'],
    ['Treatment & U=U', HeartPulse, 'https://images.pexels.com/photos/3845983/pexels-photo-3845983.jpeg?auto=compress&cs=tinysrgb&w=1200', 'Healthcare worker supporting ongoing treatment'],
    ['Rights & support', Scale, 'https://images.pexels.com/photos/4421496/pexels-photo-4421496.jpeg?auto=compress&cs=tinysrgb&w=1200', 'Friends sharing a respectful, supportive conversation'],
    ['Myths & facts', Lightbulb, 'https://images.pexels.com/photos/4421496/pexels-photo-4421496.jpeg?auto=compress&cs=tinysrgb&w=1200', 'Community members talking and learning together'],
  ] as const

  return <section className="education-center">
    <header className="education-center-hero"><div><p className="eyebrow">ARCHIVE HIV Education Center</p><h1>Understand HIV.<br /><span>Live without stigma.</span></h1><p>Accurate, inclusive information about HIV, prevention, testing, treatment, and personal rights—without judgment.</p></div><div className="education-hero-panel"><span className="education-hero-icon"><HeartPulse size={25} /></span><strong>Start where you are.</strong><p>Read one topic, save what helps, and take your next step when ready.</p><div><b>07</b><span>plain-language topics</span></div></div></header>

    <nav className="education-index" aria-label="Education topics">
      {topics.map(([label, Icon], index) => <button type="button" className={activeTopic === index ? 'active' : ''} aria-pressed={activeTopic === index} onClick={() => setActiveTopic(index)} key={label}><span>{String(index + 1).padStart(2, '0')}</span><Icon size={15} aria-hidden="true" />{label}</button>)}
    </nav>

    <figure className="education-photo-story">
      <div><img key={topics[activeTopic][2]} src={topics[activeTopic][2]} alt={topics[activeTopic][3]} loading="lazy" /></div>
      <figcaption><span>{topics[activeTopic][0]}</span><a href="https://www.pexels.com/search/healthcare%20community/" target="_blank" rel="noreferrer">Photo sourced from Pexels ↗</a></figcaption>
    </figure>

    <div className="education-progress" aria-live="polite"><span>Topic {activeTopic + 1} of {topics.length}</span><div><i style={{ width: `${((activeTopic + 1) / topics.length) * 100}%` }} /></div><strong>{topics[activeTopic][0]}</strong></div>
    <div className="education-chapters">
      <article className={activeTopic === 0 ? 'active' : ''} id="education-1"><p className="chapter-number">01</p><div><h2>HIV basics</h2><h3>HIV and AIDS are not same.</h3><p>Human Immunodeficiency Virus (HIV) attacks immune system, particularly CD4 cells that help protect against infections. Without treatment, HIV can progressively weaken immune system. Modern treatment allows people living with HIV to manage virus and live long, healthy lives.</p><ul><li>HIV is virus that affects immune system.</li><li>AIDS is most advanced stage of HIV infection.</li><li>Having HIV does not automatically mean having AIDS.</li><li>Early diagnosis and effective treatment can prevent progression to AIDS.</li></ul><div className="education-split"><section><h3>HIV can be transmitted through</h3><ul><li>Anal or vaginal sex when prevention measures are not in place.</li><li>Sharing needles, syringes, or injecting equipment.</li><li>Pregnancy, childbirth, or breastfeeding without appropriate prevention.</li></ul></section><section className="education-safe"><h3>HIV is not transmitted through</h3><ul><li>Hugging, holding hands, or casual contact.</li><li>Sharing food, glasses, utensils, toilets, or bathrooms.</li><li>Mosquito bites, sweat, tears, or ordinary social interaction.</li></ul></section></div><p className="education-reminder">HIV is a medical condition, not a reflection of someone’s character or worth.</p><Link href={sources.who}>WHO — HIV and AIDS</Link></div></article>

      <article className={`${activeTopic === 1 ? 'active' : ''} testing-topic`} id="education-2"><p className="chapter-number">02</p><div><div className="testing-heading"><span><FlaskConical size={22} /></span><div><p className="eyebrow">Know your status</p><h2>HIV testing</h2></div></div><p className="testing-intro">Testing is only reliable way to determine whether someone has HIV. A person may have HIV without noticeable symptoms.</p><div className="testing-assurances"><span><LockKeyhole size={16} /> Consent and confidentiality</span><span><BadgeCheck size={16} /> Positive screens are confirmed</span></div><h3 className="testing-window-title"><Clock3 size={18} /> Typical detection windows</h3><div className="testing-table" role="table" aria-label="Typical HIV test detection windows"><div role="row"><strong role="columnheader">HIV test</strong><strong role="columnheader">Typical window</strong></div><div role="row"><span>Nucleic Acid Test <small>NAT</small></span><b>10–33 days</b></div><div role="row"><span>Laboratory antigen/antibody</span><b>18–45 days</b></div><div role="row"><span>Rapid antigen/antibody <small>Finger-stick</small></span><b>18–90 days</b></div><div role="row"><span>Antibody test</span><b>23–90 days</b></div></div><p className="testing-note">CDC ranges shown. Recent exposure or prevention medication may affect timing. Ask a healthcare professional whether repeat testing is needed.</p><p className="education-reminder testing-reminder"><BadgeCheck size={19} /> <span><strong>Testing is responsible healthcare.</strong><br />It is nothing to be ashamed of.</span></p><Link href={sources.testing}>CDC — HIV Testing</Link></div></article>

      <article className={activeTopic === 2 ? 'active' : ''} id="education-3"><p className="chapter-number">03</p><div><h2>HIV prevention</h2><p>Prevention includes different strategies people can choose based on their needs.</p><div className="education-cards"><section><h3>Condom use</h3><p>Correct and consistent use substantially reduces HIV transmission and helps protect against several other STIs.</p></section><section><h3>Regular testing</h3><p>Knowing HIV status guides timely treatment and prevention decisions.</p></section><section><h3>PrEP and PEP</h3><p>PrEP helps before possible exposure. PEP is emergency medication after possible exposure.</p></section><section><h3>Sterile equipment</h3><p>Never sharing needles, syringes, or injecting equipment helps prevent blood-borne infections.</p></section><section><h3>Effective treatment</h3><p>People who maintain undetectable viral load do not transmit HIV through sex.</p></section></div><Link href={sources.prevention}>CDC — Preventing HIV</Link></div></article>

      <article className={activeTopic === 3 ? 'active' : ''} id="education-4"><p className="chapter-number">04</p><div><h2>PrEP and PEP</h2><div className="prep-pep"><section><span>Before exposure</span><h3>PrEP</h3><p>Medication taken by people without HIV before possible exposure. HIV testing and regular medical follow-up are needed. Availability may include oral or injectable forms. PrEP does not prevent other STIs.</p><Link href={sources.prep}>CDC — PrEP</Link></section><section><span>After exposure</span><h3>PEP</h3><p>Emergency medication started as soon as possible and no later than 72 hours after possible exposure. It is generally prescribed for 28 days after professional assessment.</p><Link href={sources.pep}>CDC — PEP</Link></section></div><aside className="urgent-note"><strong>Possible exposure within 72 hours?</strong><p>Contact an emergency department or appropriate healthcare provider immediately. Do not wait for symptoms or a routine appointment.</p></aside></div></article>

      <article className={activeTopic === 4 ? 'active' : ''} id="education-5"><p className="chapter-number">05</p><div><h2>Treatment and U=U</h2><p>Antiretroviral therapy (ART) controls HIV by preventing virus from multiplying. Starting treatment promptly and taking medication as prescribed helps maintain health and prevent complications.</p><blockquote><strong>Undetectable = Untransmittable</strong><p>A person who maintains an undetectable viral load through effective treatment does not transmit HIV through sex.</p></blockquote><ul><li>Undetectable does not mean cured.</li><li>Treatment must continue as prescribed.</li><li>Regular viral-load monitoring matters.</li><li>U=U refers to sexual HIV transmission and does not prevent other STIs.</li></ul><Link href={sources.treatment}>CDC — HIV Treatment and U=U</Link></div></article>

      <article className={activeTopic === 5 ? 'active' : ''} id="education-6"><p className="chapter-number">06</p><div><h2>Respect, rights, and support</h2><p>People living with HIV deserve dignity, privacy, respect, and equal healthcare. Republic Act No. 11166 establishes protections relating to prevention, testing, treatment, confidentiality, informed consent, and discrimination in Philippines.</p><ul><li>Protect confidential HIV-related information.</li><li>Use appropriate informed consent for testing.</li><li>Protect against discrimination based on actual or perceived status.</li><li>Support access to prevention, treatment, care, and support.</li></ul><div className="language-note"><strong>Use person-centered language</strong><p>Say “person living with HIV.” Avoid language that reduces someone to diagnosis or suggests blame.</p></div><h3>Supporting someone</h3><ul><li>Listen without judgment and respect privacy.</li><li>Never disclose HIV status without appropriate permission.</li><li>Avoid assumptions about how someone acquired HIV.</li><li>Encourage medical care and emotional support.</li></ul><div className="resource-links"><Link href={sources.law}>RA 11166 — Lawphil</Link><Link href={sources.language}>UNAIDS Terminology Guidelines</Link></div></div></article>

      <article className={activeTopic === 6 ? 'active' : ''} id="education-7"><p className="chapter-number">07</p><div><h2>HIV myths vs. facts</h2><div className="myth-list">{[
        ['HIV spreads through hugging.','HIV does not spread through hugging, handshakes, or ordinary physical contact.'],
        ['HIV and AIDS are same.','HIV is virus; AIDS is its most advanced stage when untreated infection severely damages immune system.'],
        ['A person with HIV cannot live long.','With effective treatment and consistent healthcare, people living with HIV can live long, healthy lives.'],
        ['You can tell whether someone has HIV.','HIV status cannot be determined by appearance. Testing is necessary.'],
        ['People with HIV always transmit virus.','People maintaining undetectable viral load do not transmit HIV through sex.'],
        ['HIV only affects certain groups.','HIV can affect anyone. Exposure depends on transmission routes, not identity or social group.'],
      ].map(([myth, fact]) => <section key={myth}><p><b>Myth</b>{myth}</p><p><b>Fact</b>{fact}</p></section>)}</div></div></article>
    </div>

    <div className="education-topic-controls"><button type="button" disabled={activeTopic === 0} onClick={() => { setActiveTopic(activeTopic - 1); document.querySelector('.education-index')?.scrollIntoView({ behavior: 'smooth' }) }}>← Previous topic</button><button type="button" disabled={activeTopic === topics.length - 1} onClick={() => { setActiveTopic(activeTopic + 1); document.querySelector('.education-index')?.scrollIntoView({ behavior: 'smooth' }) }}>Next topic →</button></div>

    <aside className="education-care"><div><p className="eyebrow">Need healthcare or support?</p><h2>Information is first step. Care is available.</h2><p>Explore DOH-designated treatment facilities or use ARCHIVE care guidance.</p></div><div><Link href={sources.facilities}>PNAC / DOH Treatment Facility Directory</Link><button className="home-primary" onClick={onFindCare}>Explore ARCHIVE care options</button></div></aside>
    <p className="education-disclaimer"><strong>Educational disclaimer:</strong> General health education only. This information does not replace professional medical advice, diagnosis, treatment, or emergency care.</p>
  </section>
}
