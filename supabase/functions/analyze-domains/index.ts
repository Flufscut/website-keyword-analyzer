import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'
import { DOMParser } from 'https://deno.land/x/deno_dom/deno-dom-wasm.ts'
import { corsHeaders } from '../_shared/cors.ts'

interface AnalysisResult {
  domain: string
  score: number
  status: string
  pages_crawled: number
  total_mentions: number
  redirected_to?: string
}

async function analyzeDomain(domain: string): Promise<AnalysisResult> {
  try {
    // Ensure domain starts with https://
    if (!domain.startsWith('http')) {
      domain = `https://${domain}`
    }

    // Fetch the main page
    const response = await fetch(domain, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; SalesforceAnalyzer/1.0)'
      }
    })

    if (!response.ok) {
      return {
        domain,
        score: 0,
        status: `Error: ${response.status} ${response.statusText}`,
        pages_crawled: 0,
        total_mentions: 0
      }
    }

    const html = await response.text()
    const doc = new DOMParser().parseFromString(html, 'text/html')
    if (!doc) {
      throw new Error('Failed to parse HTML')
    }

    // Count Salesforce mentions
    const text = doc.body?.textContent?.toLowerCase() || ''
    const mentions = (text.match(/salesforce/g) || []).length

    // Calculate score (simplified version)
    const score = Math.min(mentions, 10)

    return {
      domain,
      score,
      status: 'Success',
      pages_crawled: 1,
      total_mentions: mentions,
      redirected_to: response.url !== domain ? response.url : undefined
    }
  } catch (error) {
    return {
      domain,
      score: 0,
      status: `Error: ${error.message}`,
      pages_crawled: 0,
      total_mentions: 0
    }
  }
}

serve(async (req) => {
  // Handle CORS
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    if (req.method !== 'POST') {
      throw new Error('Method not allowed')
    }

    const { domains } = await req.json()
    if (!domains || !Array.isArray(domains)) {
      throw new Error('Invalid request: expected array of domains')
    }

    // Analyze all domains in parallel
    const results = await Promise.all(
      domains.map(domain => analyzeDomain(domain))
    )

    // Calculate summary statistics
    const total_domains = results.length
    const successful_domains = results.filter(r => r.status === 'Success').length
    const success_rate = (successful_domains / total_domains) * 100
    const average_score = results.reduce((acc, r) => acc + r.score, 0) / total_domains

    return new Response(
      JSON.stringify({
        results,
        summary: {
          total_domains,
          success_rate: Math.round(success_rate * 10) / 10,
          average_score: Math.round(average_score * 10) / 10
        }
      }),
      {
        headers: {
          ...corsHeaders,
          'Content-Type': 'application/json'
        }
      }
    )
  } catch (error) {
    return new Response(
      JSON.stringify({ error: error.message }),
      {
        status: 400,
        headers: {
          ...corsHeaders,
          'Content-Type': 'application/json'
        }
      }
    )
  }
}) 