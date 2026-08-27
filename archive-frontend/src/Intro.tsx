import { motion, useInView, useReducedMotion } from 'framer-motion'
import { ArrowRight } from 'lucide-react'
import { useRef } from 'react'

type Props = { onEnter: () => void }

function WordsPullUp({ text }: { text: string }) {
  const ref = useRef<HTMLHeadingElement>(null)
  const inView = useInView(ref, { once: true })
  const reduceMotion = useReducedMotion()

  return <h1 ref={ref} className="intro-title" aria-label={text}>
    {text.split(' ').map((word, index) => <motion.span
      key={word}
      aria-hidden="true"
      initial={reduceMotion ? false : { y: 50, opacity: 0 }}
      animate={inView ? { y: 0, opacity: 1 } : {}}
      transition={{ duration: .7, delay: index * .12, ease: [.16, 1, .3, 1] }}
    >{word}</motion.span>)}
  </h1>
}

export default function Intro({ onEnter }: Props) {
  const reduceMotion = useReducedMotion()
  const reveal = reduceMotion ? {} : { initial: { y: 24, opacity: 0 }, animate: { y: 0, opacity: 1 } }

  return <main className="intro">
    <video
      className="intro-video"
      src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260405_170732_8a9ccda6-5cff-4628-b164-059c500a2b41.mp4"
      autoPlay
      muted
      loop
      playsInline
      aria-hidden="true"
    />
    <div className="intro-backdrop" aria-hidden="true" />
    <div className="intro-wash" aria-hidden="true" />
    <nav className="intro-nav" aria-label="Introduction navigation">
      <span className="intro-brand"><img src="/arcHIVelogofinal.png" alt="" aria-hidden="true" /><span>arc<span>HIV</span>e</span></span>
      <button onClick={onEnter}>Enter site</button>
    </nav>
    <div className="intro-content">
      <p className="intro-kicker">For every person living with HIV. For every person seeking answers.</p>
      <WordsPullUp text="You are not alone." />
      <div className="intro-copy">
        <motion.p {...reveal} transition={{ duration: .8, delay: .5, ease: [.16, 1, .3, 1] }}>
          Your status does not define your worth. Knowledge, treatment, and stigma-free support can help you live fully—and this space can help you find them.
        </motion.p>
        <motion.button className="intro-cta" onClick={onEnter} {...reveal} transition={{ duration: .8, delay: .7, ease: [.16, 1, .3, 1] }}>
          Explore ARCHIVE <span><ArrowRight aria-hidden="true" size={19} /></span>
        </motion.button>
        <motion.ul className="intro-signals" aria-label="ARCHIVE principles" {...reveal} transition={{ duration: .8, delay: .85, ease: [.16, 1, .3, 1] }}>
          <li>Region XII</li>
          <li>Evidence-led</li>
          <li>Stigma-free</li>
        </motion.ul>
      </div>
    </div>
  </main>
}
