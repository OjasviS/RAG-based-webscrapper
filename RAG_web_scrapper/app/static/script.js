// --- Step 1 & 2: Crawl website and create vector store ---
function crawlAndIndex() {
  const urlInput = document.getElementById("url-input");
  const status = document.getElementById("crawl-status");
  const crawlBtn = document.getElementById("crawl-btn");
  const askBtn = document.getElementById("ask-btn");

  const url = urlInput.value.trim();
  if (!url) {
    alert("Please enter a website URL!");
    return;
  }

  // Disable crawl and ask buttons while processing
  crawlBtn.disabled = true;
  askBtn.disabled = true;
  crawlBtn.textContent = "Crawling...";
  status.textContent = "Starting crawl process...";

  // Step 1: Crawl
  fetch("/crawl", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      url: url,
      max_pages: 5,
      crawl_delay: 1.0
    })
  })
    .then(response => response.json())
    .then(data => {
      if (data.error) {
        throw new Error(data.error);
      }

      const seconds = data.message.match(/\((.*?)\)/)?.[1] || "unknown time";
      status.textContent = `Crawl complete. ${data.page_count} pages crawled in ${seconds}.`;

      // Step 2: Create Index
      crawlBtn.textContent = "Indexing...";
      status.textContent += " Now creating vector store...";

      return fetch("/index", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chunk_size: 800,
          chunk_overlap: 100
        })
      });
    })
    .then(response => response.json())
    .then(indexData => {
      if (indexData.error) {
        throw new Error(indexData.error);
      }

      status.textContent = `Indexing complete. ${indexData.chunk_count} chunks created. You can now ask a question.`;
      console.log("Vector store path:", indexData.vector_store_path);
    })
    .catch(error => {
      console.error("Error:", error);
      status.textContent = "Error: " + error.message;
    })
    .finally(() => {
      crawlBtn.disabled = false;
      askBtn.disabled = false;
      crawlBtn.textContent = "Crawl Website";
    });
}

// --- Step 3: Ask Question ---
function askQuestion() {
  const questionInput = document.getElementById("question-input");
  const answerBox = document.getElementById("answer-box");
  const answerText = document.getElementById("answer-text");
  const sourcesList = document.getElementById("sources");
  const askBtn = document.getElementById("ask-btn");

  const question = questionInput.value.trim();
  if (!question) {
    alert("Please enter a question!");
    return;
  }

  askBtn.disabled = true;
  askBtn.textContent = "Generating...";
  answerBox.style.display = "block";
  answerText.textContent = "Generating answer...";
  sourcesList.innerHTML = "";

  fetch("/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question: question, top_k: 3 })
  })
    .then(response => response.json())
    .then(data => {
      if (data.error) {
        answerText.textContent = "Error: " + data.error;
      } else if (data.answer) {
        answerText.textContent = data.answer;
        sourcesList.innerHTML = data.sources
          .map(s => `<li><a href="${s.url}" target="_blank">${s.url}</a></li>`)
          .join("");
      } else {
        answerText.textContent = "No answer found in crawled content.";
      }
    })
    .catch(error => {
      console.error("Error calling /ask:", error);
      answerText.textContent = "Failed to connect to server.";
    })
    .finally(() => {
      askBtn.disabled = false;
      askBtn.textContent = "Ask";
    });
}

// --- Attach Event Listeners ---
document.getElementById("crawl-btn").addEventListener("click", crawlAndIndex);
document.getElementById("ask-btn").addEventListener("click", askQuestion);