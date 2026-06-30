import { useEffect, useRef, useState } from 'react'

/**
 * Boot animation — "Document to MAP"
 *
 * Visualizes IntelliMandate's actual pipeline in ~6s:
 *   1. A circular (document) flies in and is scanned
 *   2. It fragments into 11 tier-colored dots (one per Canara Bank Wing)
 *   3. Each dot bursts outward in an elliptical radius with neural lines
 *   4. Wordmark + tagline resolve in place of the document
 */

const BOOT_BG = '#050505'
const BOOT_TEXT = '#FFFFFF'
const BOOT_TEXT_MUTED = '#5C5C63'
const BOOT_CARD_BG = '#0A0A0A'
const BOOT_BORDER = '#262626'
const BOOT_ACCENT = '#00C6FF'
const MONO_FONT = "'JetBrains Mono', monospace"

const WINGS = [
  { wing: 'Retail Banking Wing', color: '#f43f5e' },
  { wing: 'Commercial Banking Wing', color: '#f97316' },
  { wing: 'International Banking Wing', color: '#eab308' },
  { wing: 'Integrated Treasury Wing', color: '#22c55e' },
  { wing: 'Operations Wing', color: '#06b6d4' },
  { wing: 'Central Processing Wing', color: '#00C6FF' },
  { wing: 'Compliance Wing', color: '#6366f1' },
  { wing: 'Risk Management Wing', color: '#7000FF' },
  { wing: 'Financial Management Wing', color: '#a855f7' },
  { wing: 'CISO Office', color: '#ec4899' },
  { wing: 'Internal Audit Wing', color: '#f43f5e' },
].map((w, i, arr) => ({ ...w, angle: (360 / arr.length) * i }))

export default function BootAnimation({ onComplete }) {
  const [stage, setStage] = useState('enter') 
  const reducedMotion = useRef(
    typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )

  useEffect(() => {
    if (reducedMotion.current) {
      const t = setTimeout(onComplete, 400)
      return () => clearTimeout(t)
    }

    const timers = [
      setTimeout(() => setStage('scan'), 600),
      setTimeout(() => setStage('fragment'), 1650),
      setTimeout(() => setStage('route'), 2300),
      setTimeout(() => setStage('resolve'), 3700),
      setTimeout(() => setStage('exit'), 6000),
      setTimeout(() => onComplete(), 6600),
    ]
    return () => timers.forEach(clearTimeout)
  }, [onComplete])

  if (reducedMotion.current) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: BOOT_BG }}>
        <Wordmark visible showTagline />
      </div>
    )
  }

  const docVisible = stage === 'enter' || stage === 'scan'
  const fragmenting = stage === 'fragment'
  const routing = stage === 'route' || stage === 'resolve'
  const resolved = stage === 'resolve'

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center transition-opacity duration-700"
      style={{ background: BOOT_BG, opacity: stage === 'exit' ? 0 : 1, pointerEvents: stage === 'exit' ? 'none' : 'auto' }}
    >
      <div className="relative" style={{ width: 'min(1000px, 94vw)', height: 'min(700px, 82vh)' }}>
        
        {/* ── Document ── */}
        <div
          className="absolute left-1/2 top-1/2 transition-all ease-out"
          style={{
            width: 'clamp(72px, 9vw, 124px)',
            height: 'clamp(90px, 11.25vw, 155px)',
            marginLeft: 'clamp(-36px, -4.5vw, -62px)',
            marginTop: 'clamp(-45px, -5.6vw, -77px)',
            borderRadius: 12,
            background: BOOT_CARD_BG,
            border: `2px solid ${BOOT_BORDER}`,
            opacity: docVisible ? 1 : fragmenting ? 0.3 : 0,
            transform: stage === 'enter' ? 'translateY(-32px) scale(0.85)' : 'translateY(0) scale(1)',
            transitionDuration: stage === 'enter' ? '700ms' : '500ms',
            boxShadow: stage === 'scan' ? `0 0 48px ${BOOT_ACCENT}40` : 'none',
            zIndex: 2,
          }}
        >
          {[36, 60, 84, 108].map((top, i) => (
            <div key={i} className="absolute rounded-full" style={{ left: 20, top, height: 6, width: i === 3 ? 50 : 84, background: BOOT_BORDER }} />
          ))}
          {stage === 'scan' && (
            <div
              className="absolute left-0 right-0"
              style={{
                height: 3,
                background: `linear-gradient(90deg, transparent, ${BOOT_ACCENT}, transparent)`,
                animation: 'scan-sweep 1000ms ease-in-out',
                boxShadow: `0 0 12px ${BOOT_ACCENT}`,
              }}
            />
          )}
        </div>

        {/* ── Network Nodes (Dots, Lines, and Labels) ── */}
        {WINGS.map((w, i) => {
          const rad = (w.angle * Math.PI) / 180
          const scale = typeof window !== 'undefined' ? Math.min(1, window.innerWidth / 1100) : 1
          
          // 1. THE ELLIPSE: Spread horizontally (440px) to use dead space, keep vertical tight (260px)
          const rx = (routing ? 440 : fragmenting ? 64 : 0) * scale
          const ry = (routing ? 260 : fragmenting ? 64 : 0) * scale

          const x = Math.sin(rad) * rx
          const y = -Math.cos(rad) * ry

          // 2. NEURAL LINES: Calculate angle and length from center to dot
          const lineLength = Math.hypot(x, y)
          const lineAngle = Math.atan2(y, x) * (180 / Math.PI)

          // 3. SMART ANCHORING: Push text radially outward so it never overlaps the dots
          const isRight = x > 30;
          const isLeft = x < -30;
          const isBottom = y > 30;
          const isTop = y < -30;

          let textX = x;
          let textY = y;
          let translateX = '-50%'; 
          const textPushGap = 24 * scale;

          if (isRight) { translateX = '0%'; textX += textPushGap; }
          else if (isLeft) { translateX = '-100%'; textX -= textPushGap; }
          if (isBottom) { textY += textPushGap; }
          else if (isTop) { textY -= textPushGap; }

          const visible = fragmenting || routing

          return (
            <div key={w.wing}>
              {/* Neural Connecting Line */}
              <div
                className="absolute top-1/2 left-1/2"
                style={{
                  width: lineLength,
                  height: 1,
                  background: `linear-gradient(90deg, transparent 10%, ${w.color}80 90%)`,
                  transformOrigin: '0 0',
                  transform: `rotate(${lineAngle}deg)`,
                  opacity: routing ? 0.3 : 0,
                  transition: 'all 1100ms cubic-bezier(0.16, 1, 0.3, 1)',
                  transitionDelay: fragmenting ? `${i * 30}ms` : '0ms',
                  zIndex: 0,
                }}
              />

              {/* The Node (Dot) */}
              <div
                className="absolute rounded-full transition-all"
                style={{
                  left: '50%',
                  top: '50%',
                  width: 14,
                  height: 14,
                  marginLeft: -7,
                  marginTop: -7,
                  background: w.color,
                  boxShadow: `0 0 20px ${w.color}A0`,
                  opacity: visible ? 1 : 0,
                  transform: `translate(${x}px, ${y}px) scale(${visible ? 1 : 0.4})`,
                  transitionDuration: routing ? '1100ms' : '600ms',
                  transitionTimingFunction: 'cubic-bezier(0.16, 1, 0.3, 1)',
                  transitionDelay: fragmenting ? `${i * 45}ms` : '0ms',
                  zIndex: 1,
                }}
              />

              {/* Smart Label */}
              <div
                className="absolute whitespace-nowrap transition-all"
                style={{
                  left: '50%',
                  top: '50%',
                  fontFamily: MONO_FONT,
                  fontSize: 'clamp(0.6rem, 1.1vw, 0.75rem)',
                  letterSpacing: '0.04em',
                  color: w.color,
                  opacity: routing ? 0.9 : 0,
                  // Use our smart anchors instead of dumb center alignment
                  transform: `translate(${textX}px, ${textY}px) translate(${translateX}, -50%)`,
                  transitionDuration: '800ms',
                  transitionDelay: routing ? '400ms' : '0ms',
                  zIndex: 1,
                }}
              >
                {w.wing}
              </div>
            </div>
          )
        })}

        {/* ── Wordmark + tagline ── */}
        <div
          className="absolute left-1/2 top-1/2 transition-all duration-700"
          style={{ transform: 'translate(-50%, -50%)', opacity: resolved ? 1 : 0, zIndex: 3 }}
        >
          <Wordmark visible={resolved} showTagline={resolved} />
        </div>
      </div>

      <style>{`
        @keyframes scan-sweep {
          0% { top: 16px; opacity: 0; }
          15% { opacity: 1; }
          85% { opacity: 1; }
          100% { top: 140px; opacity: 0; }
        }
      `}</style>
    </div>
  )
}

function Wordmark({ visible, showTagline }) {
  return (
    <div className="flex flex-col items-center">
      <div
        className="flex items-center gap-3 whitespace-nowrap transition-transform duration-1000"
        style={{ transform: visible ? 'scale(1)' : 'scale(0.92)' }}
      >
        <span
          style={{
            fontFamily: "'Poppins', 'Inter', sans-serif",
            fontSize: 'clamp(2rem, 6vw, 4rem)',
            fontWeight: 700,
            color: BOOT_TEXT,
            letterSpacing: '-0.03em',
          }}
        >
          IntelliMandate
        </span>
      </div>
      <div
        className="whitespace-nowrap transition-all duration-1000"
        style={{
          marginTop: 14,
          fontFamily: MONO_FONT,
          fontSize: 'clamp(0.7rem, 1.8vw, 1rem)',
          letterSpacing: '0.05em',
          color: BOOT_TEXT_MUTED,
          opacity: showTagline ? 1 : 0,
          transform: showTagline ? 'translateY(0)' : 'translateY(8px)',
          transitionDelay: showTagline ? '600ms' : '0ms',
        }}
      >
        Agentic Regulatory Intelligence for Indian Banking
      </div>
    </div>
  )
}
