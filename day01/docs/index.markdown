---
layout: default
title: Day01
---

<style>
  /* =====================================================
     PAGE BACKGROUND AND VIEWPORT
     ===================================================== */

  html {
    width: 100%;
    min-height: 100%;
    background: #ffffff;
  }

  body {
    position: relative;
    min-height: 100vh;
    margin: 0;
    overflow-x: hidden;

    color: #202033;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #ffffff;
    isolation: isolate;
  }

  body::before {
    content: "";
    position: fixed;
    inset: 0;
    z-index: -1;
    pointer-events: none;

    background:
      linear-gradient(
        120deg,
        #ffffff 0%,
        #ffffff 35%,
        transparent 60%
      ),
      repeating-linear-gradient(
        135deg,
        #8b5cf6 0%,
        #06b6d4 10%,
        #ec4899 30%,
        #f97316 50%,
        #22c55e 70%,
        #6366f1 90%,
        #8b5cf6 100%
      );

    background-size:
      100% 100%,
      2000% 100%;

    background-position:
      center,
      0% 50%;

    animation: gradientShift 5s linear infinite;
  }

  @keyframes gradientShift {
    from {
      background-position:
        center,
        100% 50%;
    }

    to {
      background-position:
        center,
        0% 50%;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    body::before {
      animation: none;
    }
  }

  /* =====================================================
     HEADER AND FOOTER
     ===================================================== */

  .site-header,
  .site-footer {
    background: transparent;
    border-color: rgba(60, 50, 100, 0.15);
  }

  .site-title,
  .site-title:visited,
  .site-nav .page-link {
    color: #292344;
  }

  .site-title:hover,
  .site-nav .page-link:hover {
    color: #6d28d9;
  }

  .footer-col-wrapper,
  .footer-col {
    color: #49435f;
  }

  .footer-col a,
  .footer-col a:visited {
    color: #6d28d9;
  }

  /* =====================================================
     PAGE LAYOUT
     ===================================================== */

  .page-content {
    min-height: 0;
    box-sizing: border-box;
    padding: 24px 0;
    overflow: visible;
    background: transparent;
  }

  .wrapper {
    max-width: 1000px;
  }

  .portfolio-hero {
    margin-bottom: 24px;
    text-align: center;
  }

  .portfolio-hero .eyebrow {
    color: #5b4a91;
    font-size: 0.85rem;
    font-weight: 700;
    letter-spacing: 0.18em;
    text-transform: uppercase;
  }

  .portfolio-hero h1 {
    margin: 8px 0;
    color: #24203b;
    font-size: clamp(2rem, 5vh, 3.5rem);
    font-weight: 800;
    letter-spacing: -0.04em;
  }

  .portfolio-hero h1 span {
    color: #7955dc;
  }

  .portfolio-hero p {
    margin-bottom: 0;
    color: #49435f;
    font-size: 1.05rem;
  }

  /* =====================================================
     PORTFOLIO GRID
     ===================================================== */

  .portfolio-columns {
    display: grid;
    grid-template-columns: 1.5fr 1fr;
    gap: 24px;
    align-items: stretch;
  }

  /* =====================================================
     PORTFOLIO CARDS
     ===================================================== */

  .portfolio-card {
    height: 40vh;
    height: 40dvh;
    min-height: 0;
    min-width: 0;
    box-sizing: border-box;

    display: flex;
    flex-direction: column;

    padding: 24px;
    overflow: hidden;

    border: 1px solid rgba(255, 255, 255, 0.7);
    border-radius: 20px;
    background: rgba(255, 255, 255, 0.72);
    box-shadow: 0 12px 35px rgba(45, 30, 90, 0.12);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);

    transition:
      transform 0.25s ease,
      box-shadow 0.25s ease;
  }

  .portfolio-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 18px 42px rgba(45, 30, 90, 0.18);
  }

  /* =====================================================
     FIXED CARD TITLES
     ===================================================== */

  .portfolio-card h2 {
    flex: 0 0 auto;
    margin-top: 0;
    margin-bottom: 16px;
    color: #292344;
    font-size: 1.6rem;
  }

  /* =====================================================
     SCROLLABLE CARD CONTENT
     ===================================================== */

  .portfolio-card-content {
    flex: 1 1 auto;
    min-height: 0;
    min-width: 0;

    overflow-x: hidden;
    overflow-y: auto;
    overscroll-behavior: contain;
    overflow-wrap: anywhere;

    scrollbar-width: thin;
    scrollbar-color: rgba(121, 85, 220, 0.65) transparent;

    padding-right: 8px;
  }

  .portfolio-card-content p,
  .portfolio-card-content li {
    color: #45405b;
    line-height: 1.8;
  }

  .portfolio-card-content p:first-child {
    margin-top: 0;
  }

  .portfolio-card-content p:last-child {
    margin-bottom: 0;
  }

  .portfolio-card-content ul {
    padding-left: 24px;
  }

  .portfolio-card-content li::marker {
    color: #7955dc;
  }

  /* =====================================================
     FLOATING CIRCULAR SCROLLBAR
     ===================================================== */

  .portfolio-card-content::-webkit-scrollbar {
    width: 14px;
  }

  .portfolio-card-content::-webkit-scrollbar-track {
    background: transparent;
    border: none;
  }

  .portfolio-card-content::-webkit-scrollbar-track-piece {
    background: transparent;
  }

  .portfolio-card-content::-webkit-scrollbar-thumb {
    min-height: 28px;
    border: 4px solid transparent;
    border-radius: 50%;
    background-color: rgba(121, 85, 220, 0.65);
    background-clip: content-box;
  }

  .portfolio-card-content::-webkit-scrollbar-thumb:hover {
    background-color: rgba(109, 40, 217, 0.9);
    background-clip: content-box;
  }

  .portfolio-card-content::-webkit-scrollbar-corner {
    background: transparent;
  }

  /* =====================================================
     FIT PAGE TO VIEWPORT
     ===================================================== */

  @media (min-width: 651px) {
    html,
    body {
      height: 100%;
      min-height: 0;
      overflow: hidden;
    }

    .site-header {
      height: 56px;
      box-sizing: border-box;
    }

    .site-header .wrapper {
      height: 100%;
      box-sizing: border-box;
    }

    .site-header .site-title,
    .site-header .site-nav {
      line-height: 36px;
    }

    .page-content {
      height: calc(100dvh - 56px - 140px);
      padding: 20px 0;
      overflow: hidden;
    }

    .page-content > .wrapper {
      height: 100%;
      box-sizing: border-box;
    }

    .portfolio-hero {
      margin-bottom: 20px;
    }

    .portfolio-columns {
      grid-template-columns: 1.5fr 1fr;
    }

    .portfolio-card {
      height: 40dvh;
    }

    .site-footer {
      height: 140px;
      box-sizing: border-box;
      overflow: hidden;
      padding: 12px 0;
    }

    .site-footer .wrapper {
      box-sizing: border-box;
    }

    .site-footer .footer-col-wrapper {
      margin: 0;
      font-size: 0.8rem;
      line-height: 1.5;
    }

    .site-footer .footer-col {
      margin-bottom: 0;
    }
  }

  /* =====================================================
     RESPONSIVE DESIGN
     ===================================================== */

  @media (max-width: 650px) {
    .page-content {
      padding: 16px 0;
    }

    .portfolio-hero {
      margin-bottom: 18px;
    }

    .portfolio-hero h1 {
      font-size: clamp(1.8rem, 5vh, 2.8rem);
    }

    .portfolio-hero p {
      font-size: 0.95rem;
    }

    .portfolio-columns {
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }

    .portfolio-card {
      height: 45dvh;
      padding: 16px;
    }

    .portfolio-card h2 {
      font-size: 1.2rem;
      margin-bottom: 12px;
    }

    .portfolio-card-content p,
    .portfolio-card-content li {
      font-size: 0.9rem;
      line-height: 1.6;
    }
  }

  /* =====================================================
     SHORT VIEWPORTS
     ===================================================== */

  @media (max-height: 600px) {
    .page-content {
      padding-top: 10px;
      padding-bottom: 10px;
    }

    .portfolio-hero {
      margin-bottom: 10px;
    }

    .portfolio-hero h1 {
      font-size: 2rem;
      margin: 4px 0;
    }

    .portfolio-hero p {
      font-size: 0.9rem;
    }

    .portfolio-card {
      height: 45dvh;
      padding: 16px;
    }
  }

  /* =====================================================
     ACCESSIBILITY
     ===================================================== */

  @media (prefers-reduced-motion: reduce) {
    body::before {
      animation: none;
    }

    .portfolio-card {
      transition: none;
    }
  }
</style>

<div class="portfolio-hero">
  <div class="eyebrow">
    {{ site.portfolio.eyebrow | escape }}
  </div>

  <h1>{{ site.portfolio.name | escape }}</h1>

  <p>{{ site.portfolio.role | escape }}</p>
</div>

<div class="portfolio-columns">
  <section class="portfolio-card">
    <h2>{{ site.portfolio.about.title | escape }}</h2>

    <div class="portfolio-card-content">
      {% for paragraph in site.portfolio.about.paragraphs %}
        {{ paragraph | markdownify }}
      {% endfor %}
    </div>
  </section>

  <section class="portfolio-card">
    <h2>{{ site.portfolio.languages.title | escape }}</h2>

    <div class="portfolio-card-content">
      <ul>
        {% for language in site.portfolio.languages.items %}
          <li>{{ language | escape }}</li>
        {% endfor %}
      </ul>
    </div>
  </section>
</div>
