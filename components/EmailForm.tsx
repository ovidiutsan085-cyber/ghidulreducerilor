'use client'

import { useState } from 'react'
import { Send, CheckCircle, Loader2 } from 'lucide-react'
import { getAllStores } from '@/lib/data'

export default function EmailForm() {
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [errorMsg, setErrorMsg] = useState('')
  const stores = getAllStores()

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setStatus('loading')

    const form = e.currentTarget
    const formData = new FormData(form)

    try {
      const res = await fetch('/api/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nume: formData.get('nume'),
          email: formData.get('email'),
          magazin: formData.get('magazin'),
          gdpr_consent: true,
          consented_at: new Date().toISOString(),
        }),
      })

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.error || 'Eroare la abonare')
      }

      setStatus('success')
      form.reset()
    } catch (err) {
      setStatus('error')
      setErrorMsg(err instanceof Error ? err.message : 'Eroare necunoscută')
    }
  }

  if (status === 'success') {
    return (
      <div className="text-center py-8">
        <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-4" />
        <h3 className="font-display font-bold text-xl text-neutral-900 mb-2">
          Te-ai abonat cu succes!
        </h3>
        <p className="text-neutral-600">
          Vei primi alertele cu cele mai bune reduceri direct pe email.
        </p>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 max-w-md mx-auto">
      <div>
        <label htmlFor="nume" className="block text-sm font-medium text-neutral-700 mb-1">Nume</label>
        <input
          type="text"
          id="nume"
          name="nume"
          required
          placeholder="Numele tău"
          className="w-full px-4 py-3 rounded-xl border border-neutral-300 focus:border-brand-red focus:ring-2 focus:ring-brand-red/20 outline-none transition-all text-sm"
        />
      </div>

      <div>
        <label htmlFor="email" className="block text-sm font-medium text-neutral-700 mb-1">Email</label>
        <input
          type="email"
          id="email"
          name="email"
          required
          placeholder="email@exemplu.ro"
          className="w-full px-4 py-3 rounded-xl border border-neutral-300 focus:border-brand-red focus:ring-2 focus:ring-brand-red/20 outline-none transition-all text-sm"
        />
      </div>

      <div>
        <label htmlFor="magazin" className="block text-sm font-medium text-neutral-700 mb-1">Magazin preferat</label>
        <select
          id="magazin"
          name="magazin"
          className="w-full px-4 py-3 rounded-xl border border-neutral-300 focus:border-brand-red focus:ring-2 focus:ring-brand-red/20 outline-none transition-all text-sm bg-white"
        >
          <option value="toate">Toate magazinele</option>
          {stores.map(s => (
            <option key={s.id} value={s.id}>{s.nume}</option>
          ))}
        </select>
      </div>

      {/* GDPR Consent */}
      <div className="flex items-start gap-2">
        <input
          type="checkbox"
          id="gdpr"
          name="gdpr"
          required
          className="mt-1 rounded border-neutral-300 text-brand-red focus:ring-brand-red"
        />
        <label htmlFor="gdpr" className="text-xs text-neutral-500 leading-relaxed">
          Sunt de acord cu{' '}
          <a href="/despre#confidentialitate" className="underline hover:text-brand-red">
            politica de confidențialitate
          </a>
          {' '}și accept să primesc alerte cu reduceri pe email. Mă pot dezabona oricând.
        </label>
      </div>

      {status === 'error' && (
        <p className="text-sm text-red-600 bg-red-50 px-4 py-2 rounded-lg">{errorMsg}</p>
      )}

      <button
        type="submit"
        disabled={status === 'loading'}
        className="btn-cta w-full"
      >
        {status === 'loading' ? (
          <><Loader2 className="w-4 h-4 animate-spin" /> Se procesează...</>
        ) : (
          <><Send className="w-4 h-4" /> Abonează-mă la alerte</>
        )}
      </button>
    </form>
  )
}
