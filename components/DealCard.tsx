'use client'

import Image from 'next/image'
import { useState } from 'react'
import { ExternalLink, ImageOff } from 'lucide-react'
import { formatPrice } from '@/lib/utils'
import type { Deal } from '@/lib/data'

// Fallback placeholder cand imaginea originala e 404/broken
function FallbackImage({ title }: { title: string }) {
  return (
    <div className="absolute inset-0 bg-gradient-to-br from-neutral-100 to-neutral-200 flex flex-col items-center justify-center p-4 text-center">
      <ImageOff className="w-10 h-10 text-neutral-300 mb-2" />
      <span className="text-xs text-neutral-400 line-clamp-2">{title}</span>
    </div>
  )
}

export default function DealCard({ deal }: { deal: Deal }) {
  const [imgError, setImgError] = useState(false)
  const economie = deal.pret_original - deal.pret_redus

  return (
    <a
      href={`/out/${deal.id}`}
      target="_blank"
      rel="noopener noreferrer nofollow"
      className="card-hover overflow-hidden flex flex-col block group"
      itemScope
      itemType="https://schema.org/Product"
    >
      {/* Imagine + Badge reducere */}
      <div className="relative aspect-square bg-neutral-100 overflow-hidden">
        {imgError ? (
          <FallbackImage title={deal.titlu} />
        ) : (
          <Image
            src={deal.imagine_url}
            alt={`${deal.titlu} — reducere ${deal.procent_reducere}% de la ${formatPrice(deal.pret_original)} la ${formatPrice(deal.pret_redus)}`}
            fill
            className="object-cover group-hover:scale-105 transition-transform duration-300"
            sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 25vw"
            onError={() => setImgError(true)}
          />
        )}
        <span className="badge-discount">-{deal.procent_reducere}%</span>
      </div>

      {/* Schema microdata */}
      <meta itemProp="image" content={deal.imagine_url} />
      <meta itemProp="description" content={`${deal.titlu} — reducere ${deal.procent_reducere}% de la ${formatPrice(deal.pret_original)} la ${formatPrice(deal.pret_redus)}`} />

      {/* Conținut */}
      <div className="p-4 flex flex-col flex-1">
        <h3 className="font-display font-semibold text-neutral-900 text-sm leading-snug mb-3 line-clamp-2" itemProp="name">
          {deal.titlu}
        </h3>

        {/* Prețuri + Economie */}
        <div className="mt-auto" itemProp="offers" itemScope itemType="https://schema.org/Offer">
          <div className="flex items-baseline gap-2 mb-1">
            <span className="price-new" itemProp="price" content={String(deal.pret_redus)}>
              {formatPrice(deal.pret_redus)}
            </span>
            <span className="price-old">{formatPrice(deal.pret_original)}</span>
          </div>
          {/* Economie afișată */}
          <p className="text-xs text-emerald-600 font-medium mb-3">
            Economisești {formatPrice(economie)}
          </p>
          <meta itemProp="priceCurrency" content="RON" />
          <meta itemProp="availability" content="https://schema.org/InStock" />
          <meta itemProp="url" content={`https://ghidulreducerilor.ro/out/${deal.id}`} />
          <div itemProp="shippingDetails" itemScope itemType="https://schema.org/OfferShippingDetails" className="hidden">
            <div itemProp="shippingDestination" itemScope itemType="https://schema.org/DefinedRegion">
              <meta itemProp="addressCountry" content="RO" />
            </div>
          </div>
          <div itemProp="hasMerchantReturnPolicy" itemScope itemType="https://schema.org/MerchantReturnPolicy" className="hidden">
            <meta itemProp="applicableCountry" content="RO" />
            <meta itemProp="returnPolicyCategory" content="https://schema.org/MerchantReturnFiniteReturnWindow" />
            <meta itemProp="merchantReturnDays" content="14" />
          </div>

          <span className="btn-cta w-full text-sm">
            Vezi oferta
            <ExternalLink className="w-4 h-4" />
          </span>
        </div>
      </div>
    </a>
  )
}
