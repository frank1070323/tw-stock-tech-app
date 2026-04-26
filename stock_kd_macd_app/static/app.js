const form = document.getElementById("query-form");
const symbolInput = document.getElementById("symbol");
const targetPriceInput = document.getElementById("target-price");
const stopPriceInput = document.getElementById("stop-price");
const priceAlertInput = document.getElementById("price-alert");
const alertButton = document.getElementById("alert-button");
const alertStatus = document.getElementById("alert-status");
const statusBox = document.getElementById("status");
const resultPanel = document.getElementById("result-panel");
const chartImage = document.getElementById("chart-image");
const chartLink = document.getElementById("chart-link");
const shareLinkInput = document.getElementById("share-link");
const copyLinkButton = document.getElementById("copy-link");
const dashboardPanel = document.getElementById("dashboard-panel");

let latestPayload = null;
let alertConfig = null;
let alertIntervalId = null;

const textFields = {
  "stock-meta": function (data) { return safeText(data.market) + " | " + safeText(data.symbol); },
  "stock-title": function (data) { return safeText(data.name) + " (" + safeText(data.symbol) + ")"; },
  "company-core": function (data) { return getPath(data, ["companyProfile", "coreBusiness"]); },
  "data-date": function (data) { return safeText(data.dataDate); },
  "latest-close": function (data) { return formatNumber(data.latestClose); },
  "decision-label": function (data) { return getPath(data, ["decision", "label"]); },
  "rr-value": function (_data) { return "-"; },
  "chip-concentration-label": function (data) { return getPath(data, ["chipAnalysis", "concentration", "label"]); },
  "signal-summary": function (data) { return safeText(data.signalSummary); },
  "decision-action": function (data) { return getPath(data, ["decision", "action"]); },
  "entry-narrative": function (data) { return safeText(data.entryNarrative); },
  "profile-name": function (data) { return getPath(data, ["companyProfile", "displayName"]); },
  "profile-industry": function (data) { return getPath(data, ["companyProfile", "industry"]); },
  "profile-sector": function (data) { return getPath(data, ["companyProfile", "sectorName"]); },
  "profile-business": function (data) { return getPath(data, ["companyProfile", "coreBusiness"]); },
  "ma5-value": function (data) { return formatNumber(getPath(data, ["movingAverages", "ma5"], null)); },
  "ma10-value": function (data) { return formatNumber(getPath(data, ["movingAverages", "ma10"], null)); },
  "ma20-value": function (data) { return formatNumber(getPath(data, ["movingAverages", "ma20"], null)); },
  "ma60-value": function (data) { return formatNumber(getPath(data, ["movingAverages", "ma60"], null)); },
  "ma120-value": function (data) { return formatNumber(getPath(data, ["movingAverages", "ma120"], null)); },
  "ma-price-above": function (data) { return yesNo(getPath(data, ["movingAverageAnalysis", "priceAboveMa5"], null)); },
  "ma-bullish-stack": function (data) { return yesNo(getPath(data, ["movingAverageAnalysis", "bullishStack"], null)); },
  "ma60-direction": function (data) { return getPath(data, ["movingAverageAnalysis", "ma60Direction"]); },
  "ma120-direction": function (data) { return getPath(data, ["movingAverageAnalysis", "ma120Direction"]); },
  "kd-brief": function (data) { return "K " + formatNumber(data.k) + " / D " + formatNumber(data.d); },
  "kd-direction": function (data) { return safeText(data.kdDirection); },
  "kd-curve": function (data) { return safeText(data.kdCurve); },
  "kd-signal": function (data) {
    const signal = safeText(data.kdSignal);
    const lowZone = yesNo(data.kdLowZone);
    return signal + " | 低檔區：" + lowZone;
  },
  "macd-brief": function (data) {
    return "DIF " + formatNumber(data.dif) + " / DEA " + formatNumber(data.dea) + " / OSC " + formatNumber(data.osc);
  },
  "macd-direction": function (data) { return safeText(data.macdDirection); },
  "macd-curve": function (data) { return safeText(data.macdCurve); },
  "macd-zero-axis": function (data) { return safeText(data.macdZeroAxis); },
  "latest-volume": function (data) { return formatLots(data.latestVolumeLots); },
  "vma5-value": function (data) { return formatLots(getPath(data, ["volumeAverages", "vma5"], null)); },
  "vma20-value": function (data) { return formatLots(getPath(data, ["volumeAverages", "vma20"], null)); },
  "volume-ratio": function (data) { return formatRatio(getPath(data, ["volumeAnalysis", "ratioToVma5"], null)); },
  "volume-burst": function (data) { return yesNo(getPath(data, ["volumeAnalysis", "burst"], null)); },
  "volume-vma20": function (data) { return yesNo(getPath(data, ["volumeAnalysis", "aboveVma20"], null)); },
  "score-volume": function (data) { return safeText(getPath(data, ["score", "volume"], "-")) + "/3"; },
  "atr14-value": function (data) { return formatNumber(getPath(data, ["supportResistance", "atr14"], null)); },
  "atr-stop-value": function (data) { return formatNumber(getPath(data, ["supportResistance", "atrStopLoss"], null)); },
  "suggested-stop-value": function (data) { return formatNumber(getPath(data, ["supportResistance", "suggestedStopLoss"], null)); },
  "max-volume-support": function (data) { return formatNumber(getPath(data, ["supportResistance", "maxVolumeSupport"], null)); },
  "key-bull-support": function (data) { return formatNumber(getPath(data, ["supportResistance", "keyBullBarSupport"], null)); },
  "quarter-low-support": function (data) { return formatNumber(getPath(data, ["supportResistance", "quarterLowSupport"], null)); },
  "quarter-high-resistance": function (data) { return formatNumber(getPath(data, ["supportResistance", "quarterHighResistance"], null)); },
  "risk-target": function (data) { return formatNumber(getPath(data, ["riskPlan", "targetPrice"], null)); },
  "risk-stop": function (data) { return formatNumber(getPath(data, ["riskPlan", "stopPrice"], null)); },
  "risk-reward": function (data) { return formatNumber(getPath(data, ["riskPlan", "rewardAmount"], null)); },
  "risk-risk": function (data) { return formatNumber(getPath(data, ["riskPlan", "riskAmount"], null)); },
  "risk-rr": function (data) { return formatRatio(getPath(data, ["riskPlan", "rrRatio"], null)); },
  "risk-note": function (data) { return getPath(data, ["riskPlan", "note"]); },
  "chip-foreign": function (data) { return formatBuyDays("外資", getPath(data, ["chipAnalysis", "foreignBuyDays"], null), getPath(data, ["chipAnalysis", "available"], false)); },
  "chip-trust": function (data) { return formatBuyDays("投信", getPath(data, ["chipAnalysis", "trustBuyDays"], null), getPath(data, ["chipAnalysis", "available"], false)); },
  "chip-dealer": function (data) { return formatBuyDays("自營商", getPath(data, ["chipAnalysis", "dealerBuyDays"], null), getPath(data, ["chipAnalysis", "available"], false)); },
  "chip-latest": function (data) { return formatChipLatest(getPath(data, ["chipAnalysis"], null)); },
  "chip-concentration-5": function (data) { return formatSignedMaybe(getPath(data, ["chipAnalysis", "concentration", "days5"], null)); },
  "chip-concentration-10": function (data) { return formatSignedMaybe(getPath(data, ["chipAnalysis", "concentration", "days10"], null)); },
  "chip-concentration-20": function (data) { return formatSignedMaybe(getPath(data, ["chipAnalysis", "concentration", "days20"], null)); },
  "chip-concentration-note": function (data) { return getPath(data, ["chipAnalysis", "concentration", "note"]); },
  "chip-narrative": function (data) { return getPath(data, ["chipAnalysis", "narrative"]); },
  "fund-pe": function (data) { return formatMaybe(getPath(data, ["fundamentals", "pe"], null)); },
  "fund-pe-position": function (data) { return getPath(data, ["fundamentals", "pePosition"]); },
  "fund-pb": function (data) { return formatMaybe(getPath(data, ["fundamentals", "pbRatio"], null)); },
  "fund-yield": function (data) { return formatPercentMaybe(getPath(data, ["fundamentals", "dividendYield"], null)); },
  "fund-yoy": function (data) { return formatPercentMaybe(getPath(data, ["fundamentals", "revenueYoY"], null)); },
  "fund-mom": function (data) { return formatPercentMaybe(getPath(data, ["fundamentals", "revenueMoM"], null)); },
  "fund-narrative": function (data) { return getPath(data, ["fundamentals", "narrative"]); },
  "backtest-trades": function (data) { return safeText(getPath(data, ["backtest", "closedTrades"], "-")) + " 筆"; },
  "backtest-winrate": function (data) { return formatPercentMaybe(getPath(data, ["backtest", "winRate"], null)); },
  "backtest-avg": function (data) { return formatPercentMaybe(getPath(data, ["backtest", "avgReturn"], null)); },
  "backtest-best": function (data) { return formatPercentMaybe(getPath(data, ["backtest", "bestTrade"], null)); },
  "backtest-worst": function (data) { return formatPercentMaybe(getPath(data, ["backtest", "worstTrade"], null)); },
  "backtest-note": function (data) { return getPath(data, ["backtest", "note"]); },
  "holding-position": function (data) { return yesNo(getPath(data, ["exitAnalysis", "holdingPosition"], null)); },
  "exit-signals": function (data) { return joinOrDash(getPath(data, ["exitAnalysis", "activeSignals"], [])); },
  "exit-warnings": function (data) { return joinOrDash(getPath(data, ["exitAnalysis", "activeWarnings"], [])); },
  "last-trade": function (data) { return formatTrade(getPath(data, ["exitAnalysis", "lastTrade"], null)); },
  "dashboard-label": function (data) { return getPath(data, ["dashboard", "label"]); },
  "dashboard-headline": function (data) { return getPath(data, ["dashboard", "headline"]); },
  "dashboard-score": function (data) { return getPath(data, ["dashboard", "scoreHint"]); },
  "sentiment-count": function (data) { return safeText(getPath(data, ["sentiment", "newsCount7d"], "-")); },
  "sentiment-label-2": function (data) { return getPath(data, ["sentiment", "label"]); },
  "sentiment-narrative": function (data) { return getPath(data, ["sentiment", "narrative"]); },
};

if (form) {
  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    const symbol = trimValue(symbolInput);
    if (!symbol) {
      setStatus("請輸入股票代號。", "error");
      if (resultPanel) {
        resultPanel.classList.add("hidden");
      }
      return;
    }
    await runQuery(symbol, false);
  });
}

if (alertButton) {
  alertButton.addEventListener("click", function () {
    if (!latestPayload) {
      setAlertStatus("請先查詢股票。");
      return;
    }
    const value = toOptionalNumber(priceAlertInput ? priceAlertInput.value : "");
    if (value === null) {
      setAlertStatus("請輸入有效提醒價格。");
      return;
    }
    alertConfig = {
      symbol: latestPayload.symbol,
      name: latestPayload.name,
      target: value,
      triggered: false,
    };
    setAlertStatus("已設定 " + latestPayload.name + " (" + latestPayload.symbol + ") 到價提醒：" + value.toFixed(2));
    ensureAlertPolling();
  });
}

if (copyLinkButton) {
  copyLinkButton.addEventListener("click", async function () {
    if (!shareLinkInput || !shareLinkInput.value) {
      return;
    }
    try {
      await navigator.clipboard.writeText(shareLinkInput.value);
      setStatus("分享連結已複製。", "success");
    } catch (_error) {
      setStatus("複製失敗，請手動複製。", "error");
    }
  });
}

async function runQuery(symbol, silent) {
  if (!silent) {
    setStatus("查詢中...", "");
  }

  try {
    const url = new URL("/api/analyze", window.location.origin);
    url.searchParams.set("symbol", symbol);
    appendRiskParams(url.searchParams);

    const response = await fetch(url.toString(), { cache: "no-store" });
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload && payload.error ? payload.error : "查詢失敗");
    }

    latestPayload = payload;
    renderResult(payload, symbol);

    if (!silent) {
      setStatus("查詢完成。", "success");
    }

    return payload;
  } catch (error) {
    if (!silent) {
      setStatus(error && error.message ? error.message : "查詢失敗", "error");
      if (resultPanel) {
        resultPanel.classList.add("hidden");
      }
    }
    throw error;
  }
}

function renderResult(data, symbol) {
  for (const id in textFields) {
    if (!Object.prototype.hasOwnProperty.call(textFields, id)) {
      continue;
    }
    const node = document.getElementById(id);
    if (!node) {
      continue;
    }
    node.textContent = textFields[id](data);
  }

  if (dashboardPanel && data.dashboard) {
    dashboardPanel.className = "dashboard-panel " + safeText(data.dashboard.tone || "neutral");
  }

  renderTags(document.getElementById("status-tags"), data.statusTags, true);
  renderTags(document.getElementById("theme-tags"), mapLabelsToTags(getPath(data, ["companyProfile", "themes"], []), "neutral"), true);
  renderTags(document.getElementById("chip-tags"), mapLabelsToTags(getPath(data, ["chipAnalysis", "tags"], []), "positive"), true);
  renderPeers(document.getElementById("peer-list"), getPath(data, ["peerComparison"], []));
  renderExitRules(document.getElementById("exit-rules"), getPath(data, ["exitAnalysis", "rules"], {}));
  renderSentimentItems(document.getElementById("sentiment-items"), getPath(data, ["sentiment", "items"], []));
  applyCostAnalysis(data);
  renderChart(symbol);

  if (shareLinkInput) {
    shareLinkInput.value = buildShareLink(symbol);
  }
  history.replaceState({}, "", buildPathWithParams(symbol));

  if (resultPanel) {
    resultPanel.classList.remove("hidden");
  }
}

function renderTags(container, tags, tagsAreObjects) {
  if (!container) {
    return;
  }
  container.innerHTML = "";
  if (!tags || !tags.length) {
    return;
  }
  for (let i = 0; i < tags.length; i += 1) {
    const tag = tags[i];
    const span = document.createElement("span");
    const tone = tagsAreObjects ? safeText(tag.tone || "neutral") : "neutral";
    span.className = "tag " + tone;
    span.textContent = tagsAreObjects ? safeText(tag.label) : safeText(tag);
    container.appendChild(span);
  }
}

function renderPeers(container, peers) {
  if (!container) {
    return;
  }
  container.innerHTML = "";
  if (!peers || !peers.length) {
    container.textContent = "目前沒有同族群比較資料。";
    return;
  }
  for (let i = 0; i < peers.length; i += 1) {
    const peer = peers[i];
    const row = document.createElement("div");
    row.className = "peer-item";
    const tone = Number(peer.changePercent || 0) >= 0 ? "positive-text" : "danger-text";
    row.innerHTML =
      "<div><strong>" + safeText(peer.rank) + ". " + safeText(peer.name) + " (" + safeText(peer.symbol) + ")</strong>" +
      "<span>" + safeText(peer.market) + " | " + safeText(peer.role) + "</span></div>" +
      "<strong class=\"" + tone + "\">" + formatSigned(Number(peer.changePercent || 0)) + "%</strong>";
    container.appendChild(row);
  }
}

function renderExitRules(container, rules) {
  if (!container) {
    return;
  }
  container.innerHTML = "";
  const items = [
    "跌破 MA5：" + formatMaybe(getPath(rules, ["priceTrigger"], null)),
    "KD 訊號：" + safeText(getPath(rules, ["kdTrigger"], "-")),
    "量能訊號：" + safeText(getPath(rules, ["volumeTrigger"], "-")),
    "移動停利：" + safeText(getPath(rules, ["trailingStopTrigger"], "-")),
    "MA20 訊號：" + safeText(getPath(rules, ["ma20Trigger"], "-")),
  ];
  for (let i = 0; i < items.length; i += 1) {
    const item = document.createElement("div");
    item.className = "rule-item";
    item.textContent = items[i];
    container.appendChild(item);
  }
}

function renderSentimentItems(container, items) {
  if (!container) {
    return;
  }
  container.innerHTML = "";
  if (!items || !items.length) {
    container.textContent = "目前沒有額外情緒事件。";
    return;
  }
  for (let i = 0; i < items.length; i += 1) {
    const item = document.createElement("div");
    item.className = "rule-item";
    if (items[i] && typeof items[i] === "object") {
      const title = safeText(items[i].title);
      const publishedAt = safeText(items[i].publishedAt);
      item.textContent = publishedAt !== "-" ? publishedAt.slice(0, 10) + " | " + title : title;
    } else {
      item.textContent = safeText(items[i]);
    }
    container.appendChild(item);
  }
}

function renderChart(symbol) {
  const chartUrl = new URL("/api/chart", window.location.origin);
  chartUrl.searchParams.set("symbol", symbol);
  chartUrl.searchParams.set("t", String(Date.now()));
  if (chartImage) {
    chartImage.src = chartUrl.toString();
  }
  if (chartLink) {
    chartLink.href = chartUrl.toString();
  }
}

function appendRiskParams(params) {
  params.delete("target_price");
  params.delete("stop_price");
}

function ensureAlertPolling() {
  if (alertIntervalId) {
    return;
  }
  alertIntervalId = window.setInterval(async function () {
    if (!alertConfig) {
      return;
    }
    try {
      const payload = await runQuery(alertConfig.symbol, true);
      checkAlert(payload);
    } catch (_error) {
      // ignore
    }
  }, 60000);
}

function checkAlert(data) {
  if (!alertConfig || alertConfig.triggered || !data || alertConfig.symbol !== data.symbol) {
    return;
  }
  if (Number(data.latestClose || 0) >= Number(alertConfig.target)) {
    alertConfig.triggered = true;
    const message = safeText(data.name) + " 已到達提醒價格 " + Number(alertConfig.target).toFixed(2);
    setAlertStatus(message);
    window.alert(message);
    if ("speechSynthesis" in window) {
      const utterance = new SpeechSynthesisUtterance(message);
      utterance.lang = "zh-TW";
      window.speechSynthesis.speak(utterance);
    }
  }
}

function setStatus(message, type) {
  if (!statusBox) {
    return;
  }
  statusBox.textContent = message || "";
  statusBox.className = type ? "status " + type : "status";
}

function setAlertStatus(message) {
  if (alertStatus) {
    alertStatus.textContent = message;
  }
}

function buildShareLink(symbol) {
  return window.location.origin + buildPathWithParams(symbol);
}

function buildPathWithParams(symbol) {
  const url = new URL(window.location.href);
  url.searchParams.set("symbol", symbol);
  const cost = toOptionalNumber(targetPriceInput ? targetPriceInput.value : "");
  if (cost !== null) {
    url.searchParams.set("cost_price", String(cost));
  } else {
    url.searchParams.delete("cost_price");
  }
  return url.pathname + "?" + url.searchParams.toString();
}

function getPath(obj, path, fallback) {
  let current = obj;
  for (let i = 0; i < path.length; i += 1) {
    if (current === null || current === undefined || !Object.prototype.hasOwnProperty.call(current, path[i])) {
      return fallback === undefined ? "-" : fallback;
    }
    current = current[path[i]];
  }
  if (current === null || current === undefined || current === "") {
    return fallback === undefined ? "-" : fallback;
  }
  return current;
}

function safeText(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return String(value);
}

function trimValue(node) {
  return node && typeof node.value === "string" ? node.value.trim() : "";
}

function yesNo(value) {
  if (value === true) {
    return "是";
  }
  if (value === false) {
    return "否";
  }
  return "-";
}

function joinOrDash(values) {
  return values && values.length ? values.join("、") : "-";
}

function formatNumber(value) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(2) : "-";
}

function formatMaybe(value) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(2) : "-";
}

function formatSignedMoney(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "-";
  }
  return value >= 0 ? "+" + value.toFixed(2) : value.toFixed(2);
}

function formatLots(value) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(2) + " 張" : "-";
}

function formatPercentMaybe(value) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(2) + "%" : "-";
}

function formatRatio(value) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(2) + " 倍" : "-";
}

function formatSigned(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "-";
  }
  return value >= 0 ? "+" + value.toFixed(2) : value.toFixed(2);
}

function formatSignedMaybe(value) {
  return typeof value === "number" && Number.isFinite(value) ? formatSigned(value) : "-";
}

function formatBuyDays(label, days, available) {
  if (!available) {
    return "-";
  }
  const numericDays = typeof days === "number" && Number.isFinite(days) ? days : 0;
  return numericDays > 0 ? label + " 連買 " + numericDays + " 天" : label + " 暫無連買";
}

function formatChipLatest(chipAnalysis) {
  if (!chipAnalysis || !chipAnalysis.available || !chipAnalysis.latest) {
    return "-";
  }
  const latest = chipAnalysis.latest;
  return "外資 " + formatSigned(Number(latest.foreign_net || 0)) +
    " / 投信 " + formatSigned(Number(latest.trust_net || 0)) +
    " / 自營商 " + formatSigned(Number(latest.dealer_net || 0));
}

function formatTrade(trade) {
  if (!trade) {
    return "-";
  }
  const side = trade.type === "buy" ? "買進" : "賣出";
  return safeText(trade.date) + " | " + side + " | " + safeText(trade.reason);
}

function toOptionalNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? number : null;
}

function mapLabelsToTags(labels, tone) {
  const results = [];
  if (!labels || !labels.length) {
    return results;
  }
  for (let i = 0; i < labels.length; i += 1) {
    results.push({ label: labels[i], tone: tone });
  }
  return results;
}

function initializeFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const symbol = (params.get("symbol") || "").trim();
  const cost = params.get("cost_price") || params.get("target_price");

  tuneLegacyLayout();

  if (targetPriceInput && cost) {
    targetPriceInput.value = cost;
  }
  if (shareLinkInput) {
    shareLinkInput.value = buildShareLink(symbol || "");
  }
  if (!symbol) {
    return;
  }
  if (symbolInput) {
    symbolInput.value = symbol;
  }
  runQuery(symbol, false);
}

initializeFromUrl();

function tuneLegacyLayout() {
  const costLabel = document.querySelector('label[for="target-price"]');
  if (costLabel) {
    costLabel.textContent = "成本價";
  }
  if (targetPriceInput) {
    targetPriceInput.placeholder = "例如 188";
  }

  const stopLabel = document.querySelector('label[for="stop-price"]');
  const stopWrapper = stopPriceInput && stopPriceInput.parentElement ? stopPriceInput.parentElement : null;
  if (stopLabel && stopLabel.parentElement) {
    stopLabel.parentElement.style.display = "none";
  } else if (stopWrapper) {
    stopWrapper.style.display = "none";
  }

  const queryHint = document.querySelector(".field-note");
  if (queryHint) {
    queryHint.textContent = "請先輸入股票代號；成本價填你的進場成本，系統會自動分析目前盈虧、建議停損與持股狀態。";
  }

  renameLabelByValueId("rr-value", "成本報酬");
  renameLabelByValueId("risk-target", "成本價");
  renameLabelByValueId("risk-stop", "建議停損");
  renameLabelByValueId("risk-reward", "目前損益");
  renameLabelByValueId("risk-risk", "報酬率");
  renameLabelByValueId("risk-rr", "距停損空間");
}

function renameLabelByValueId(valueId, newLabel) {
  const valueNode = document.getElementById(valueId);
  if (!valueNode) {
    return;
  }
  const row = valueNode.closest(".metric-row");
  if (row) {
    const dt = row.querySelector("dt");
    if (dt) {
      dt.textContent = newLabel;
      return;
    }
  }
  const summaryItem = valueNode.closest(".summary-item");
  if (summaryItem) {
    const label = summaryItem.querySelector("span");
    if (label) {
      label.textContent = newLabel;
    }
  }
}

function applyCostAnalysis(data) {
  const cost = toOptionalNumber(targetPriceInput ? targetPriceInput.value : "");
  if (!cost) {
    setNodeText("rr-value", "-");
    setNodeText("risk-target", "-");
    setNodeText("risk-stop", formatNumber(getPath(data, ["supportResistance", "suggestedStopLoss"], null)));
    setNodeText("risk-reward", "-");
    setNodeText("risk-risk", "-");
    setNodeText("risk-rr", "-");
    setNodeText("risk-note", "輸入你的成本價後，系統會自動換算目前盈虧、報酬率與建議停損。");
    return;
  }

  const latestClose = Number(data.latestClose || 0);
  const suggestedStop = getPath(data, ["supportResistance", "suggestedStopLoss"], null);
  const quarterResistance = getPath(data, ["supportResistance", "quarterHighResistance"], null);
  const pnlAmount = latestClose - cost;
  const pnlPercent = cost > 0 ? (pnlAmount / cost) * 100 : null;
  const roomToStop = typeof suggestedStop === "number" ? latestClose - suggestedStop : null;
  const roomToResistance = typeof quarterResistance === "number" ? quarterResistance - latestClose : null;
  const activeSignals = getPath(data, ["exitAnalysis", "activeSignals"], []);

  let note = "現價與成本接近，先觀察是否重新站穩五日線與量能。";
  if (activeSignals && activeSignals.length) {
    note = "目前已出現出場訊號：" + activeSignals.join("、") + "。若這是你的持股，建議先以風控為主。";
  } else if (pnlPercent !== null && pnlPercent >= 10) {
    note = "目前明顯獲利中，可續抱觀察，但建議用系統建議停損守住成果。";
  } else if (pnlPercent !== null && pnlPercent > 0) {
    note = "目前仍在成本之上，屬小幅獲利，留意是否跌破五日線或量價轉弱。";
  } else if (pnlPercent !== null && pnlPercent <= -8) {
    note = "目前已明顯低於成本，若同時跌破技術支撐，應優先檢查風控。";
  } else if (pnlPercent !== null && pnlPercent < 0) {
    note = "目前落在成本下方，但還可以對照五日線、季線與建議停損來判斷是否續抱。";
  }

  if (roomToResistance !== null && roomToResistance < 0) {
    note += " 現價已靠近或超過近季高壓力，留意高檔震盪。";
  }

  setNodeText("rr-value", formatPercentMaybe(pnlPercent));
  setNodeText("risk-target", formatNumber(cost));
  setNodeText("risk-stop", formatNumber(suggestedStop));
  setNodeText("risk-reward", formatSignedMoney(pnlAmount));
  setNodeText("risk-risk", formatPercentMaybe(pnlPercent));
  setNodeText("risk-rr", formatNumber(roomToStop));
  setNodeText("risk-note", note);
}

function setNodeText(id, value) {
  const node = document.getElementById(id);
  if (node) {
    node.textContent = value;
  }
}
