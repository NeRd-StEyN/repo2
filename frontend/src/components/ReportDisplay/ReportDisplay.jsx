import React, { useEffect, useState, useRef } from "react";
import "./ReportDisplay.css";

export const ReportDisplay = ({
  topic,
  pdfUrl,
  setPdfUrl,
  reportText,
  setReportText,
  language,
  pageCount,
  isGenerating
}) => {
  const [pdfBlobUrl, setPdfBlobUrl] = useState("");
  const [isMobile, setIsMobile] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editedText, setEditedText] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [selection, setSelection] = useState({ start: 0, end: 0, text: "", visible: false, x: 0, y: 0 });
  const [isRewriting, setIsRewriting] = useState(false);
  const textAreaRef = useRef(null);


  useEffect(() => {
    const checkMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
    setIsMobile(checkMobile);
  }, []);


  useEffect(() => {
    if (pdfUrl) {
      // If it's a data URI, convert to blob to avoid long URLs and browser restrictions
      if (pdfUrl.startsWith("data:application/pdf")) {
        try {
          const base64Data = pdfUrl.replace(/^data:application\/pdf;base64,/, "");
          const byteCharacters = atob(base64Data);
          const byteNumbers = Array.from(byteCharacters, (c) => c.charCodeAt(0));
          const byteArray = new Uint8Array(byteNumbers);
          const blob = new Blob([byteArray], { type: "application/pdf" });
          const blobUrl = URL.createObjectURL(blob);
          setPdfBlobUrl(blobUrl);

          // Cleanup old blob URL
          return () => URL.revokeObjectURL(blobUrl);
        } catch (err) {
          console.error("Error converting PDF base64:", err);
          setPdfBlobUrl(pdfUrl);
        }
      } else {
        // If it's already a regular URL or blob URL, use it directly
        setPdfBlobUrl(pdfUrl);
      }
    }
  }, [pdfUrl]);


  useEffect(() => {
    if (reportText) {
      setEditedText(reportText);
    }
  }, [reportText]);


  const openPdfInNewTab = () => {
    let viewUrl = "";
    if (topic && language && pageCount) {
      const cacheKey = encodeURIComponent(`${topic}||${language}||${pageCount}`);
      viewUrl = `/api/report/view/${cacheKey}`;
    } else if (pdfBlobUrl) {
      viewUrl = pdfBlobUrl;
    }

    if (viewUrl) {
      const link = document.createElement("a");
      link.href = viewUrl;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } else {
      alert("PDF not ready for viewing yet.");
    }
  };


  const handleDownload = () => {
    if (!pdfBlobUrl) return;
    const link = document.createElement("a");
    link.href = pdfBlobUrl;
    link.download = `${topic || "report"}.pdf`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };
  const preventAutoScroll = () => {

    window.scrollTo({ top: 0, behavior: "instant" });
  };


  const handleSave = async () => {
    if (!reportText && !editedText) return;
    setIsSaving(true);
    setSaveError("");

    const cacheKey = `${topic}||${language}||${pageCount}`;

    try {
      const response = await fetch("/api/report/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cache_key: cacheKey,
          report_text: editedText,
          language: language
        }),
      });

      if (!response.ok) throw new Error("Failed to save report");

      const data = await response.json();
      if (data.pdf_base64) {
        setPdfUrl(`data:application/pdf;base64,${data.pdf_base64}`);
        setReportText(data.report_text);
        setIsEditing(false);
      }
    } catch (err) {
      console.error("Error saving report:", err);
      setSaveError("Failed to save changes. Please try again.");
    } finally {
      setIsSaving(false);
    }
  };



  const handleTextSelection = (e) => {
    const el = e.target;
    const start = el.selectionStart;
    const end = el.selectionEnd;
    const selectedText = (el.value.substring(start, end) || "").trim();

    if (selectedText.length >= 2) {
      // Basic positioning logic for the rewrite button
      // We'll use more robust positioning in CSS and JS later if needed
      setSelection({
        start,
        end,
        text: selectedText,
        visible: true,
        x: e.clientX || 0,
        y: e.clientY || 0
      });
    } else {
      setSelection(prev => ({ ...prev, visible: false }));
    }
  };


  // Reset to View mode when a new report is generated
  useEffect(() => {
    if (!isGenerating && pdfUrl) {
      setIsEditing(false);
    }
  }, [isGenerating, pdfUrl]);


  const handleRewrite = async () => {
    if (!selection.text || isRewriting) return;

    setIsRewriting(true);
    const originalText = selection.text;
    const startIdx = selection.start;
    const endIdx = selection.end;

    // Clear selection UI early
    setSelection(prev => ({ ...prev, visible: false }));

    try {
      const resp = await fetch("/api/report/rewrite", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: originalText,
          language: language
        }),
      });

      if (!resp.ok) throw new Error("Rewrite failed");

      const data = await resp.json();
      const fullRewrittenText = data.rewritten_text;

      if (fullRewrittenText) {
        setEditedText(prev => {
          return prev.substring(0, startIdx) + fullRewrittenText + prev.substring(endIdx);
        });
      }

    } catch (err) {
      console.error("Rewrite error:", err);
      alert("Failed to rewrite segment.");
    } finally {
      setIsRewriting(false);
    }
  };


  return (
    <div className="report-display">
      <div className="report-header">
        <h3>Preview Report</h3>
        {!isGenerating && pdfUrl && (
          <button
            className={`edit-toggle-btn ${isEditing ? 'active' : ''}`}
            onClick={() => setIsEditing(!isEditing)}
            disabled={isSaving}
          >
            {isEditing ? "👁️ View PDF" : "✏️ Edit Text"}
          </button>
        )}
      </div>

      <div className="report-content">
        {isGenerating && (
          <div className="generating-placeholder">
            <div className="loading-spinner"></div>
            <p>⏳ AI is generating your report...</p>
            <p className="loading-subtext">This may take a few moments</p>
          </div>
        )}

        {!isGenerating && pdfUrl && (
          <>
            {isEditing ? (
              <div className="report-editor-container">
                <textarea
                  ref={textAreaRef}
                  className="report-editor"
                  value={editedText}
                  onChange={(e) => setEditedText(e.target.value)}
                  onMouseUp={handleTextSelection}
                  onKeyUp={handleTextSelection}
                  placeholder="Edit report content here..."
                  spellCheck="false"
                />

                {selection.visible && (
                  <button
                    className="floating-rewrite-btn"
                    style={{
                      position: 'fixed',
                      left: `${selection.x}px`,
                      top: `${selection.y - 45}px`,
                      zIndex: 1000
                    }}
                    onClick={handleRewrite}
                    disabled={isRewriting}
                  >
                    {isRewriting ? "✨ Rewriting..." : "✨ Rewrite with AI"}
                  </button>
                )}

                <div className="editor-actions">
                  {saveError && <span className="save-error">{saveError}</span>}
                  <button
                    className="save-btn"
                    onClick={handleSave}
                    disabled={isSaving}
                  >
                    {isSaving ? "Saving..." : "💾 Save Changes"}
                  </button>
                </div>
              </div>
            ) : (
              <div className="pdf-placeholder">
                <div className="pdf-icon">📄</div>
                <div className="pdf-info">
                  <h4>Report Ready</h4>
                  <p>Your document has been generated and is ready for viewing.</p>
                </div>
                <div className="pdf-view-actions">
                  <button className="view-new-tab-btn" onClick={openPdfInNewTab}>
                    👁️ View PDF in New Tab
                  </button>
                  <button className="download-btn" onClick={handleDownload}>
                    ⬇️ Download PDF
                  </button>
                </div>
              </div>
            )}
          </>
        )}

        {!isGenerating && !pdfUrl && (
          <div className="empty-state">
            <div className="empty-icon">📝</div>
            <p>No report generated yet</p>
            <p className="empty-subtext">
              Start by generating a report from the left panel
            </p>
          </div>
        )}
      </div>
    </div >
  );
};
