// ─── 全局状态 ──────────────────────────────────────────────

let spreads = {}
let selectedSpread = null
let currentReadingId = null
let cardImages = {}
let captchaToken = null  // 当前验证码 token

// ─── 初始化 ──────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  try {
    const imgResp = await fetch('/static/card_images.json')
    cardImages = await imgResp.json()
  } catch (e) {
    console.warn('卡牌图片加载失败:', e)
  }

  try {
    const resp = await fetch('/api/spreads')
    const data = await resp.json()
    spreads = {}
    for (const s of data.spreads) {
      spreads[s.id] = s
    }
    renderSpreads()
  } catch (e) {
    console.error('加载牌阵失败:', e)
  }
})

// ─── 步骤切换 ────────────────────────────────────────────

function goStep(n) {
  document.querySelectorAll('.step-section').forEach(s => s.classList.remove('active'))
  document.getElementById(`step${n}`).classList.add('active')

  document.querySelectorAll('.step-item').forEach(s => s.classList.remove('active'))
  document.querySelector(`.step-item[data-step="${n}"]`).classList.add('active')
}

// ─── 渲染牌阵 ────────────────────────────────────────────

function renderSpreads() {
  const grid = document.getElementById('spread-grid')
  grid.innerHTML = ''

  const iconList = [
    '◈', '♡', '♢', '♤', '♧', '☽', '☯', '❋',
    '✧', '✦', '❖', '✤', '≋', '⟡', '⊹'
  ]

  let i = 0
  for (const [id, s] of Object.entries(spreads)) {
    const div = document.createElement('div')
    div.className = 'spread-card'
    div.dataset.id = id
    div.innerHTML =
      `<div class="card-icon">${iconList[i % iconList.length]}</div>` +
      `<div class="name">${s.name}</div>` +
      `<div class="count">${s.cardCount} 张牌</div>` +
      (s.description ? `<div class="desc">${s.description}</div>` : '')
    div.addEventListener('click', () => selectSpread(id))
    grid.appendChild(div)
    i++
  }
}

function selectSpread(id) {
  document.querySelectorAll('.spread-card').forEach(c => c.classList.remove('selected'))
  const card = document.querySelector(`.spread-card[data-id="${id}"]`)
  if (card) card.classList.add('selected')
  selectedSpread = id
  goStep(2)
}

// ─── 验证码 ──────────────────────────────────────────────

async function fetchCaptcha() {
  const errEl = document.getElementById('captcha-error')
  errEl.classList.add('hidden')
  captchaToken = null
  document.getElementById('captcha-problem').textContent = '加载中...'
  document.getElementById('captcha-input').value = ''
  try {
    const resp = await fetch('/api/captcha')
    const data = await resp.json()
    if (data.token) {
      captchaToken = data.token
      document.getElementById('captcha-problem').textContent = data.problem
    } else {
      // Redis 不可用，跳过验证码
      captchaToken = '__skip__'
      document.getElementById('captcha-problem').textContent = ''
    }
  } catch (e) {
    // 网络错误，跳过验证码
    captchaToken = '__skip__'
    document.getElementById('captcha-problem').textContent = ''
  }
}

// 每次进入 step2 时刷新验证码
const _origGoStep = goStep
goStep = function(n) {
  _origGoStep(n)
  if (n === 2) fetchCaptcha()
}

// ─── 渲染牌面 ────────────────────────────────────────────

function renderCards(cards) {
  const grid = document.getElementById('card-grid')
  grid.innerHTML = ''

  for (const card of cards) {
    const div = document.createElement('div')
    const reversed = card.isReversed || card.reversed
    div.className = `card-item ${reversed ? 'reversed' : 'upright'}`

    const numKey = String(card.number)
    const imgFile = cardImages[numKey] || ''
    const imgSrc = imgFile ? `/static/cards/${imgFile}.jpg` : ''

    div.innerHTML =
      `<div class="card-position">${card.position || ''}</div>` +
      (imgSrc
        ? `<div class="card-img-wrapper"><img src="${imgSrc}" alt="${card.name}" class="card-img${reversed ? ' reversed' : ''}" loading="lazy"></div>`
        : '') +
      `<div class="card-name">${card.name}${reversed ? ' 逆位' : ''}</div>` +
      `<div class="card-meaning">${card.meaning || ''}</div>`

    grid.appendChild(div)
  }
}

// ─── 开始占卜（流式） ─────────────────────────────────────

async function startReading() {
  const question = document.getElementById('question-input').value.trim()
  if (!question) {
    document.getElementById('question-input').focus()
    return
  }
  if (!selectedSpread) {
    goStep(1)
    return
  }

  const btn = document.getElementById('draw-btn')
  btn.disabled = true
  btn.textContent = '占卜中'

  // 切换到结果页
  goStep(3)
  document.getElementById('reading-question').textContent = `「${question}」`
  document.getElementById('card-grid').innerHTML = ''
  document.getElementById('reading-text').innerHTML = ''
  document.getElementById('ai-reading').classList.add('hidden')
  document.getElementById('typing-indicator').classList.remove('hidden')

  try {
    const resp = await fetch('/api/reading', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        spread_id: selectedSpread,
        question,
        captcha_token: captchaToken || '',
        captcha_answer: document.getElementById('captcha-input').value.trim()
      }),
    })

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ error: '请求失败' }))
      // 验证码错误 → 显示在验证码区域并刷新
      if (err.error && err.error.includes('验证码')) {
        document.getElementById('captcha-error').textContent = err.error
        document.getElementById('captcha-error').classList.remove('hidden')
        fetchCaptcha()
      } else {
        document.getElementById('reading-text').textContent = err.error || '服务器错误，请稍后再试'
        document.getElementById('ai-reading').classList.remove('hidden')
        document.getElementById('typing-indicator').classList.add('hidden')
      }
      btn.disabled = false
      btn.textContent = '开始占卜'
      return
    }

    // --- SSE 流式读取 ---
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let cardsRendered = false
    let textStarted = false
    const textEl = document.getElementById('reading-text')
    const indicator = document.getElementById('typing-indicator')

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || ''

      for (const event of parts) {
        if (!event.startsWith('data: ')) continue
        try {
          const d = JSON.parse(event.slice(6))

          // 牌面数据 — 图片和位置信息先到
          if (d.cards && !cardsRendered) {
            renderCards(d.cards)
            cardsRendered = true
          }

          // 流式 token — 文本开始
          if (d.token) {
            if (!textStarted) {
              indicator.classList.add('hidden')
              document.getElementById('ai-reading').classList.remove('hidden')
              textStarted = true
            }
            const buf = textEl.dataset.mdBuffer || ''
            textEl.dataset.mdBuffer = buf + d.token
            textEl.innerHTML = marked.parse(textEl.dataset.mdBuffer)
          }

          // 完成信号
          if (d.done) {
            currentReadingId = d.reading_id
            if (d.cards) renderCards(d.cards)
            indicator.classList.add('hidden')
            document.getElementById('ai-reading').classList.remove('hidden')
            if (textEl.dataset.mdBuffer) {
              textEl.innerHTML = marked.parse(textEl.dataset.mdBuffer)
            }
          }
        } catch (e) {
          // partial JSON — ignore
        }
      }
    }
  } catch (e) {
    document.getElementById('reading-text').textContent = '网络错误，请检查连接后重试'
    document.getElementById('ai-reading').classList.remove('hidden')
  }

  btn.disabled = false
  btn.textContent = '开始占卜'
}

// ─── 重置 ────────────────────────────────────────────────

function resetAll() {
  selectedSpread = null
  currentReadingId = null
  document.getElementById('question-input').value = ''
  document.getElementById('char-count').textContent = '0'
  document.querySelectorAll('.spread-card').forEach(c => c.classList.remove('selected'))
  const textEl = document.getElementById('reading-text')
  delete textEl.dataset.mdBuffer
  goStep(1)
}

// ─── 字数统计 ────────────────────────────────────────────

document.getElementById('question-input').addEventListener('input', function () {
  document.getElementById('char-count').textContent = this.value.length
})

// ─── 验证码刷新 ──────────────────────────────────────────

document.getElementById('captcha-refresh').addEventListener('click', fetchCaptcha)
