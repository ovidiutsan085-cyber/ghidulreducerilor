'use client'

import { useState, useEffect, useRef } from 'react'
import { X, Bell, CheckCircle } from 'lucide-react'

export default function ExitIntentPopup() {
  const [visible, setVisible] = useState(false)
  const [email, setEmail] = useState('')
  const [nume, setNume] = useState('')
  const [gdpr, setGdpr] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [loading, setLoading] = useState(false)
  const shown = useRef(false)

  useEffect(() => {
    // Nu afisa daca a fost deja vazut in aceasta sesiune
    if (sessionStorage.getItem('exit_popup_shown')) return

    // Desktop: exit intent la mouse leave din fereastra
    const handleMouseLeave = (e: MouseEvent) => {
      if (e.clientY <= 0 && !shown.current) {
        shown.current = true
        setVisible(true)
        sessionStorage.setItem('exit_popup_shown', '1')
      }
    }

    // Mobil: afisare la 60% scroll depth
    const handleScroll = () => {
      if (shown.current) return
      const scrolled = window.scrollY / (document.documentElement.scrollHeight - window.innerHeight)
      if (scrolled >= 0.6) {
        shown.current = true
        setVisible(true)
        sessionStorage.setItem('exit_popup_shown', '1')
      }
    }

    // Delay de 3s inainte de a activa listenerele
    const timer = setTimeout(() => {
      document.addEventListener('mouseleave', handleMouseLeave)
      window.addEventListener('scroll', handleScroll, { passive: true })
    }, 3000)

    return () => {
      clearTimeout(timer)
      document.removeEventListener('mouseleave', handleMouseLeave)
      window.removeEventListener('scroll', handleScroll)
    }
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email) return
    setLoading(true)
    try {
      await fetch('/api/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, nume: nume || 'Abonat', magazin: 'toate', gdpr_consent: true, consented_at: new Date().toISOString(), source: 'exit_popup' }),
      })
      setSubmitted(true)
    } finally {
      setLoading(false)
    }
  }

  if (!visible) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="bg-white rounded-3xl shadow-2xl max-w-md w-full p-8 relative">
        <button
          onClick={() => setVisible(false)}
          className="absolute top-4 right-4 text-neutral-400 hover:text-neutral-600 transition-colors"
          aria-label="Inchide"
        >
          <X className="w-5 h-5" />
        </button>

        {submitted ? (
          <div className="text-center py-4">
            <CheckCircle className="w-14 h-14 text-emerald-500 mx-auto mb-4" />
            <h3 className="font-display font-bold text-2xl text-neutral-900 mb-2">Ești abonat!</h3>
            <p className="text-neutral-500">Vei primi cele mai bune reduceri direct pe email.</p>
            <button
              onClick={() => setVisible(false)}
              className="mt-6 btn-cta w-full"
            >
              Super, mulțumesc!
            </button>
          </div>
        ) : (
          <>
            <div className="text-center mb-6">
              <div className="w-16 h-16 bg-brand-red/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <Bell className="w-8 h-8 text-brand-red" />
              </div>
              <h3 className="font-display font-bold text-2xl text-neutral-900 mb-2">
                Nu pleca fără cadoul tău! 🎁
              </h3>
              <p className="text-neutral-500 text-sm leading-relaxed">
                Abonează-te <strong>gratuit</strong> și primești:
              </p>
            </div>

            <ul className="space-y-2 mb-6 text-sm">
              {[
                'Top 10 oferte zilnice pe email',
                'Alertă instant la flash sales',
                'Coduri exclusive pentru abonați',
              ].map(item => (
                <li key={item} className="flex items-center gap-2 text-neutral-700">
                  <CheckCircle className="w-4 h-4 text-emerald-500 shrink-0" />
                  {item}
                </li>
              ))}
            </ul>

            <form onSubmit={handleSubmit} className="space-y-3">
              <input
                type="text"
                value={nume}
                onChange={e => setNume(e.target.value)}
                placeholder="Numele tău"
                required
                className="w-full border border-neutral-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-red/30"
              />
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="email@exemplu.ro"
                required
                className="w-full border border-neutral-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-red/30"
              />
              <label className="flex items-start gap-2 text-xs text-neutral-500">
                <input
                  type="checkbox"
                  checked={gdpr}
                  onChange={e => setGdpr(e.target.checked)}
                  required
                  className="mt-0.5 rounded border-neutral-300 text-brand-red focus:ring-brand-red"
                />
                <span>
                  Sunt de acord cu{' '}
                  <a href="/despre#confidentialitate" className="underline hover:text-brand-red">politica de confidențialitate</a>
                  . Mă pot dezabona oricând.
                </span>
              </label>
              <button type="submit" disabled={loading || !gdpr} className="btn-cta w-full">
                {loading ? 'Se abonează...' : 'Mă abonez — E GRATUIT'}
              </button>
              <button
                type="button"
                onClick={() => setVisible(false)}
                className="w-full text-xs text-neutral-400 hover:text-neutral-600 py-1"
              >
                Nu, prefer să plătesc mai mult
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  )
}
