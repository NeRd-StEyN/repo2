import React, { useEffect, useRef, useState } from 'react';
import * as pdfjsLib from 'pdfjs-dist';

// Set up the worker from the public directory
pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs';

const PdfViewer = ({ pdfData }) => {
    const canvasRef = useRef(null);
    const [numPages, setNumPages] = useState(0);
    const [currentPage, setCurrentPage] = useState(1);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const pdfDocRef = useRef(null);

    const containerRef = useRef(null);

    useEffect(() => {
        const loadPdf = async () => {
            if (!pdfData) return;
            setLoading(true);
            setError(null);
            try {
                let loadingTask;
                if (pdfData.startsWith('data:application/pdf;base64,')) {
                    const base64Data = pdfData.replace(/^data:application\/pdf;base64,/, '');
                    const binaryData = atob(base64Data);
                    const uint8Array = new Uint8Array(binaryData.length);
                    for (let i = 0; i < binaryData.length; i++) {
                        uint8Array[i] = binaryData.charCodeAt(i);
                    }
                    loadingTask = pdfjsLib.getDocument({ data: uint8Array });
                } else {
                    loadingTask = pdfjsLib.getDocument(pdfData);
                }

                const pdf = await loadingTask.promise;
                pdfDocRef.current = pdf;
                setNumPages(pdf.numPages);
                setCurrentPage(1);
                await renderPage(1, pdf);
            } catch (err) {
                console.error('Error loading PDF:', err);
                setError('Failed to load PDF. Try downloading instead.');
            } finally {
                setLoading(false);
            }
        };

        loadPdf();
    }, [pdfData]);

    // Handle resize for responsiveness
    useEffect(() => {
        const handleResize = () => {
            if (pdfDocRef.current) {
                renderPage(currentPage);
            }
        };
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, [currentPage]);

    const renderPage = async (pageNo, pdf = pdfDocRef.current) => {
        if (!pdf || !canvasRef.current || !containerRef.current) return;

        try {
            const page = await pdf.getPage(pageNo);
            const containerWidth = containerRef.current.clientWidth - 48; // Padding

            // Calculate initial scale to fit container width
            const unscaledViewport = page.getViewport({ scale: 1 });
            const scale = containerWidth / unscaledViewport.width;

            // Increase scale for high-DPI screens (retina) to keep it sharp
            const outputScale = window.devicePixelRatio || 1;
            const viewport = page.getViewport({ scale: Math.min(scale, 1.5) * outputScale });

            const canvas = canvasRef.current;
            const context = canvas.getContext('2d');

            canvas.width = Math.floor(viewport.width);
            canvas.height = Math.floor(viewport.height);
            canvas.style.width = Math.floor(viewport.width / outputScale) + "px";
            canvas.style.height = Math.floor(viewport.height / outputScale) + "px";

            const renderContext = {
                canvasContext: context,
                viewport: viewport,
                transform: outputScale !== 1 ? [outputScale, 0, 0, outputScale, 0, 0] : null
            };

            await page.render(renderContext).promise;
        } catch (err) {
            console.error('Error rendering page:', err);
        }
    };

    const changePage = (offset) => {
        const newPage = currentPage + offset;
        if (newPage >= 1 && newPage <= numPages) {
            setCurrentPage(newPage);
            renderPage(newPage);
        }
    };

    return (
        <div ref={containerRef} className="pdf-viewer-container" style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '1.2rem',
            padding: '1rem',
            background: '#111',
            flex: 1,
            width: '100%',
            overflowY: 'auto',
            overflowX: 'hidden',
            minHeight: 0,
            scrollbarWidth: 'thin',
            scrollbarColor: '#444 transparent'
        }}>
            {loading && (
                <div className="pdf-loading-state" style={{ color: '#aaa', marginTop: '2rem' }}>
                    <div className="loading-spinner" style={{ margin: '0 auto 1rem' }}></div>
                    Processing PDF content...
                </div>
            )}

            {error && (
                <div className="pdf-error-state" style={{
                    color: '#ff4d4d',
                    background: 'rgba(255, 77, 77, 0.1)',
                    padding: '1rem',
                    borderRadius: '8px',
                    border: '1px solid rgba(255, 77, 77, 0.2)',
                    textAlign: 'center'
                }}>
                    <p>{error}</p>
                </div>
            )}

            {!loading && !error && (
                <>
                    <div className="pdf-controls" style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '1.5rem',
                        background: 'rgba(255, 255, 255, 0.05)',
                        backdropFilter: 'blur(10px)',
                        padding: '10px 20px',
                        borderRadius: '12px',
                        position: 'sticky',
                        top: 0,
                        zIndex: 10,
                        border: '1px solid rgba(255, 255, 255, 0.1)',
                        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.3)'
                    }}>
                        <button
                            onClick={() => changePage(-1)}
                            disabled={currentPage <= 1}
                            style={{
                                background: currentPage <= 1 ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.1)',
                                border: 'none',
                                color: currentPage <= 1 ? '#666' : 'white',
                                borderRadius: '8px',
                                padding: '6px 14px',
                                cursor: currentPage <= 1 ? 'not-allowed' : 'pointer',
                                transition: 'all 0.2s',
                                fontSize: '0.9rem',
                                fontWeight: '600'
                            }}
                        >
                            ← Previous
                        </button>
                        <span style={{ fontSize: '0.9rem', color: '#ccc', fontWeight: '500' }}>
                            Page <span style={{ color: '#fff', fontWeight: '700' }}>{currentPage}</span> of {numPages}
                        </span>
                        <button
                            onClick={() => changePage(1)}
                            disabled={currentPage >= numPages}
                            style={{
                                background: currentPage >= numPages ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.1)',
                                border: 'none',
                                color: currentPage >= numPages ? '#666' : 'white',
                                borderRadius: '8px',
                                padding: '6px 14px',
                                cursor: currentPage >= numPages ? 'not-allowed' : 'pointer',
                                transition: 'all 0.2s',
                                fontSize: '0.9rem',
                                fontWeight: '600'
                            }}
                        >
                            Next →
                        </button>
                    </div>

                    <div className="canvas-wrapper" style={{
                        boxShadow: '0 10px 40px rgba(0, 0, 0, 0.5)',
                        borderRadius: '4px',
                        background: 'white',
                        lineHeight: 0,
                        maxWidth: '100%',
                        overflow: 'hidden'
                    }}>
                        <canvas ref={canvasRef} style={{ maxWidth: '100%', height: 'auto' }} />
                    </div>
                </>
            )}
        </div>
    );
};

export default PdfViewer;
