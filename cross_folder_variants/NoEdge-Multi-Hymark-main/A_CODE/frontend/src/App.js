import React, { useState, useEffect, useCallback } from 'react';
import {
  Upload,
  FileText,
  CheckCircle,
  Clock,
  AlertCircle,
  Download,
  ChevronRight,
  BookOpen,
  Zap,
  RefreshCw,
  X,
  FileArchive,
  Target,
  Award,
  TrendingUp,
  Eye,
  Link,
  Lock,
  Globe,
  Play,
  PenTool,
  Plus,
  Trash2,
  FileCheck,
  Loader
} from 'lucide-react';
import './App.css';

const API_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:3001';

// API helper with timeout support
const api = {
  async get(endpoint) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 120000);

    try {
      const res = await fetch(`${API_URL}${endpoint}`, { signal: controller.signal });
      clearTimeout(timeoutId);

      if (!res.ok) throw new Error(`API Error: ${res.status} when hitting ${endpoint}`);

      const contentType = res.headers.get("content-type");
      if (contentType && contentType.includes("application/json")) {
        return res.json();
      }

      return {}; // Return empty object fallback if server sent back string text
    } catch (error) {
      clearTimeout(timeoutId);
      if (error.name === 'AbortError') {
        throw new Error('Request timed out. Please try again.');
      }
      throw error;
    }
  },
  async post(endpoint, data, isFormData = false) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 180000);

    const options = {
      method: 'POST',
      body: isFormData ? data : JSON.stringify(data),
      signal: controller.signal,
    };
    if (!isFormData) {
      options.headers = { 'Content-Type': 'application/json' };
    }

    try {
      const res = await fetch(`${API_URL}${endpoint}`, options);
      clearTimeout(timeoutId);

      // 1. If the request failed, handle it intelligently
      if (!res.ok) {
        const contentType = res.headers.get("content-type");
        if (contentType && contentType.includes("application/json")) {
          const jsonError = await res.json();
          // Extract FastAPI's specific detail array if present
          const message = jsonError.detail ? JSON.stringify(jsonError.detail) : "Unknown backend error";
          throw new Error(message);
        } else {
          const errorText = await res.text();
          throw new Error(errorText || `Server Error Status: ${res.status}`);
        }
      }

      // 2. Safe parsing of success data
      const successContentType = res.headers.get("content-type");
      if (successContentType && successContentType.includes("application/json")) {
        return await res.json();
      }

      throw new Error("Server succeeded but failed to return a valid JSON payload.");

    } catch (error) {
      clearTimeout(timeoutId);
      if (error.name === 'AbortError') {
        throw new Error('Assessment is taking longer than expected. Please try again.');
      }
      throw error;
    }
  }
};


// Toast notification component
function Toast({ message, type, onClose }) {
    useEffect(() => {
      const timer = setTimeout(onClose, 4000);
      return () => clearTimeout(timer);
    }, [onClose]);

const icons = {
  success: <CheckCircle size={18} />,
  error: <AlertCircle size={18} />,
  info: <Clock size={18} />
};

return (
  <div className={`toast toast-${type}`} data-testid="toast-notification">
    {icons[type]}
    <span>{message}</span>
    <button onClick={onClose} className="toast-close">
      <X size={16} />
    </button>
  </div>
);
}

// Job Results Modal - shows per-student breakdown
function JobResultsModal({ job, onClose, onDownload }) {
  const [expandedStudent, setExpandedStudent] = useState(null);
  const assessments = job.results?.assessments || [];

  // Sort by score descending
  const sortedAssessments = [...assessments].sort((a, b) => (b.percentage || 0) - (a.percentage || 0));

  // Calculate stats
  const stats = assessments.length > 0 ? {
    count: assessments.length,
    avgScore: assessments.reduce((sum, a) => sum + (a.percentage || 0), 0) / assessments.length,
    minScore: Math.min(...assessments.map(a => a.percentage || 0)),
    maxScore: Math.max(...assessments.map(a => a.percentage || 0)),
    passCount: assessments.filter(a => (a.percentage || 0) >= 50).length
  } : null;

  const getScoreColor = (percentage) => {
    if (percentage >= 75) return '#22c55e';
    if (percentage >= 60) return '#84cc16';
    if (percentage >= 50) return '#eab308';
    return '#ef4444';
  };

  return (
    <div className="modal-overlay" onClick={onClose} data-testid="job-results-modal">
      <div className="modal-content modal-large" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2><Award size={24} /> Assessment Results: {job.job_id}</h2>
          <button className="modal-close" onClick={onClose}><X size={24} /></button>
        </div>

        {stats && (
          <div className="results-stats-bar">
            <div className="stat-item">
              <span className="stat-value">{stats.count}</span>
              <span className="stat-label">Students</span>
            </div>
            <div className="stat-item">
              <span className="stat-value" style={{ color: getScoreColor(stats.avgScore) }}>
                {stats.avgScore.toFixed(1)}%
              </span>
              <span className="stat-label">Average</span>
            </div>
            <div className="stat-item">
              <span className="stat-value">{stats.minScore.toFixed(0)}% - {stats.maxScore.toFixed(0)}%</span>
              <span className="stat-label">Range</span>
            </div>
            <div className="stat-item">
              <span className="stat-value">{stats.passCount}/{stats.count}</span>
              <span className="stat-label">Pass (≥50%)</span>
            </div>
          </div>
        )}

        <div className="modal-body">
          <div className="students-list">
            {sortedAssessments.map((assessment, index) => (
              <div
                key={assessment.student_id || index}
                className={`student-result-card ${expandedStudent === index ? 'expanded' : ''}`}
              >
                <div
                  className="student-result-header"
                  onClick={() => setExpandedStudent(expandedStudent === index ? null : index)}
                >
                  <div className="student-info">
                    <span className="student-rank">#{index + 1}</span>
                    <span className="student-id">{assessment.student_id || 'Unknown'}</span>
                    {assessment.group_members && (
                      <span className="group-badge">Group ({assessment.group_members.length + 1} members)</span>
                    )}
                  </div>
                  <div className="student-score" style={{ backgroundColor: getScoreColor(assessment.percentage || 0) }}>
                    {assessment.total_score || 0} / {job.results?.total_marks || 25}
                    <span className="score-pct">({(assessment.percentage || 0).toFixed(0)}%)</span>
                  </div>
                  <ChevronRight size={20} className={`expand-icon ${expandedStudent === index ? 'rotated' : ''}`} />
                </div>

                {expandedStudent === index && (
                  <div className="student-result-details">
                    {/* Criteria breakdown */}
                    {assessment.criteria_scores && (
                      <div className="criteria-breakdown">
                        <h4>Criteria Scores</h4>
                        {Object.entries(assessment.criteria_scores).map(([name, data]) => (
                          <div key={name} className="criterion-row">
                            <span className="criterion-name">{name}</span>
                            <span className="criterion-level">{data.level}</span>
                            <span className="criterion-score">{data.score}</span>
                            {data.feedback && (
                              <p className="criterion-feedback">{data.feedback}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Strengths */}
                    {assessment.strengths && assessment.strengths.length > 0 && (
                      <div className="feedback-section strengths">
                        <h4><CheckCircle size={16} /> Strengths</h4>
                        <ul>
                          {assessment.strengths.map((s, i) => <li key={i}>{s}</li>)}
                        </ul>
                      </div>
                    )}

                    {/* Areas for improvement */}
                    {assessment.areas_for_improvement && assessment.areas_for_improvement.length > 0 && (
                      <div className="feedback-section improvements">
                        <h4><TrendingUp size={16} /> Areas for Improvement</h4>
                        <ul>
                          {assessment.areas_for_improvement.map((a, i) => <li key={i}>{a}</li>)}
                        </ul>
                      </div>
                    )}

                    {/* Overall feedback */}
                    {assessment.overall_feedback && (
                      <div className="overall-feedback">
                        <h4>Overall Feedback</h4>
                        <p>{assessment.overall_feedback}</p>
                      </div>
                    )}

                    {/* Group members */}
                    {assessment.group_members && (
                      <div className="group-members">
                        <h4>Group Members (same grade applied)</h4>
                        <div className="member-ids">
                          {assessment.group_members.map(id => (
                            <span key={id} className="member-id">{id}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn-secondary" onClick={onClose}>Close</button>
          <button className="btn-primary" onClick={() => onDownload(job.job_id)}>
            <Download size={18} /> Download Graded ZIP
          </button>
        </div>
      </div>
    </div>
  );
}

// Live Progress Overlay for bulk assessment
function LiveProgressOverlay({ jobId, progress, onClose }) {
  const getScoreColor = (percentage) => {
    if (percentage >= 75) return '#22c55e';
    if (percentage >= 60) return '#84cc16';
    if (percentage >= 50) return '#eab308';
    return '#ef4444';
  };

  const assessments = progress?.results?.assessments || [];
  const total = progress?.total || progress?.results?.total_submissions || 0;
  const processed = progress?.progress || assessments.length;
  const percentComplete = total > 0 ? (processed / total) * 100 : 0;

  return (
    <div className="live-progress-overlay" data-testid="live-progress-overlay">
      <div className="live-progress-container">
        <div className="live-progress-header">
          <RefreshCw size={28} className="spin" style={{ color: '#e85d04' }} />
          <h2>Processing Assessments</h2>
        </div>

        <div className="live-progress-stats">
          <div className="live-stat">
            <span className="live-stat-value">{processed}</span>
            <span className="live-stat-label">Processed</span>
          </div>
          <div className="live-stat">
            <span className="live-stat-value">{total}</span>
            <span className="live-stat-label">Total</span>
          </div>
          <div className="live-stat">
            <span className="live-stat-value">{percentComplete.toFixed(0)}%</span>
            <span className="live-stat-label">Complete</span>
          </div>
        </div>

        <div className="live-progress-bar-container">
          <div className="live-progress-bar">
            <div
              className="live-progress-fill"
              style={{ width: `${percentComplete}%` }}
            />
          </div>
          <div className="live-progress-text">
            <span>Job ID: {jobId}</span>
            <span>{processed} of {total} submissions</span>
          </div>
        </div>

        {progress?.current_student && (
          <div className="live-current-student">
            <h4>Currently Processing:</h4>
            <p>Student {progress.current_student.id} - {progress.current_student.file}</p>
          </div>
        )}

        {assessments.length > 0 && (
          <div className="live-completed-list">
            {assessments.slice(-5).reverse().map((a, i) => (
              <div key={i} className="live-completed-item">
                <span className="student-id">{a.student_id}</span>
                <span
                  className="student-score"
                  style={{ backgroundColor: getScoreColor(a.percentage || 0) }}
                >
                  {a.total_score}/{progress?.results?.total_marks || 25} ({(a.percentage || 0).toFixed(0)}%)
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// Rubric Detail Card with expandable criteria
function RubricDetailCard({ rubric }) {
  const [expandedCriterion, setExpandedCriterion] = useState(null);

  return (
    <div className="rubric-detail-card" data-testid={`rubric-detail-${rubric._id}`}>
      <div className="rubric-detail-header">
        <BookOpen size={24} />
        <div>
          <h3>{rubric.name}</h3>
          <span className="rubric-meta">
            {rubric.total_marks} total marks | {rubric.criteria?.length || 0} criteria
          </span>
        </div>
      </div>
      {rubric.criteria?.length > 0 && (
        <div className="criteria-list">
          <h4>Criteria (click to expand):</h4>
          <div className="criteria-items">
            {rubric.criteria.map((criterion, i) => (
              <div key={i} className="criterion-item">
                <div
                  className={`criterion-header ${expandedCriterion === i ? 'expanded' : ''}`}
                  onClick={() => setExpandedCriterion(expandedCriterion === i ? null : i)}
                >
                  <ChevronRight size={16} className={`criterion-chevron ${expandedCriterion === i ? 'rotated' : ''}`} />
                  <span className="criterion-name">{criterion.name}</span>
                  <span className="criterion-weight">({criterion.weight} marks)</span>
                </div>
                {expandedCriterion === i && criterion.levels && (
                  <div className="criterion-levels">
                    {Object.entries(criterion.levels).map(([levelName, levelData]) => (
                      <div key={levelName} className="level-row">
                        <span className="level-name">{levelName}</span>
                        <span className="level-score">
                          {Number(levelData.min_score).toFixed(1)}-{Number(levelData.max_score).toFixed(1)}
                        </span>
                        <span className="level-description">{levelData.description}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// File upload dropzone
function FileDropzone({ onFileSelect, accept, label, icon: Icon }) {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) {
      setSelectedFile(file);
      onFileSelect(file);
    }
  }, [onFileSelect]);

  const handleFileInput = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedFile(file);
      onFileSelect(file);
    }
  };

  return (
    <div
      className={`dropzone ${isDragging ? 'dropzone-active' : ''} ${selectedFile ? 'dropzone-selected' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      data-testid="file-dropzone"
    >
      <input
        type="file"
        accept={accept}
        onChange={handleFileInput}
        className="dropzone-input"
        data-testid="file-input"
      />
      <Icon size={32} className="dropzone-icon" />
      {selectedFile ? (
        <div className="dropzone-selected-info">
          <span className="selected-filename">{selectedFile.name}</span>
          <span className="selected-size">{(selectedFile.size / 1024).toFixed(1)} KB</span>
        </div>
      ) : (
        <>
          <span className="dropzone-label">{label}</span>
          <span className="dropzone-hint">Drop file or click to browse</span>
        </>
      )}
    </div>
  );
}

// Rubric display card
function RubricCard({ rubric, isSelected, onSelect }) {
  return (
    <div
      className={`rubric-card ${isSelected ? 'rubric-card-selected' : ''}`}
      onClick={() => onSelect(rubric)}
      data-testid={`rubric-card-${rubric._id}`}
    >
      <div className="rubric-card-header">
        <BookOpen size={20} />
        <span className="rubric-name">{rubric.name}</span>
      </div>
      <div className="rubric-card-body">
        <div className="rubric-stat">
          <Target size={14} />
          <span>{rubric.total_marks} marks</span>
        </div>
        <div className="rubric-stat">
          <FileText size={14} />
          <span>{rubric.criteria?.length || 0} criteria</span>
        </div>
      </div>
      {isSelected && (
        <div className="rubric-selected-badge">
          <CheckCircle size={16} />
          Selected
        </div>
      )}
    </div>
  );
}

// Assessment result card
function AssessmentResultCard({ assessment, onViewDetails }) {
  const getScoreColor = (percentage) => {
    if (percentage >= 75) return 'score-excellent';
    if (percentage >= 60) return 'score-good';
    if (percentage >= 50) return 'score-satisfactory';
    return 'score-needs-work';
  };

  return (
    <div className="assessment-card" data-testid={`assessment-${assessment.student_id}`}>
      <div className="assessment-header">
        <div className="student-info">
          <span className="student-id">{assessment.student_id || 'Unknown'}</span>
          <span className="submission-file">{assessment.submission_file}</span>
        </div>
        <div className={`score-badge ${getScoreColor(assessment.percentage)}`}>
          <Award size={16} />
          {assessment.total_score?.toFixed(1)} / {assessment.max_score || 100}
        </div>
      </div>
      <div className="assessment-body">
        <div className="percentage-bar">
          <div
            className={`percentage-fill ${getScoreColor(assessment.percentage)}`}
            style={{ width: `${Math.min(assessment.percentage, 100)}%` }}
          />
          <span className="percentage-text">{assessment.percentage?.toFixed(1)}%</span>
        </div>
        {assessment.strengths?.length > 0 && (
          <div className="feedback-preview">
            <strong>Strengths:</strong> {assessment.strengths[0]}
          </div>
        )}
      </div>
      <button
        className="view-details-btn"
        onClick={() => onViewDetails(assessment)}
        data-testid={`view-details-${assessment.student_id}`}
      >
        <Eye size={16} />
        View Details
      </button>
    </div>
  );
}

// Assessment details modal
function AssessmentDetailsModal({ assessment, onClose }) {
  if (!assessment) return null;

  const handleDownload = () => {
    if (assessment._id) {
      const link = document.createElement('a');
      link.href = `${API_URL}/api/assessment/${assessment._id}/download`;
      link.download = `${assessment.submission_file || 'assessment'}_graded.docx`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()} data-testid="assessment-details-modal">
        <button className="modal-close" onClick={onClose}>
          <X size={24} />
        </button>

        <div className="modal-header">
          <h2>Assessment Details</h2>
          <div className="modal-student-info">
            <span>Student: {assessment.student_id}</span>
            <span>File: {assessment.submission_file}</span>
          </div>
        </div>

        <div className="modal-score-section">
          <div className="big-score">
            <span className="score-value">{assessment.total_score?.toFixed(1)}</span>
            <span className="score-max">/ {assessment.max_score || 100}</span>
          </div>
          <div className="score-percentage">
            {assessment.percentage?.toFixed(1)}%
          </div>
        </div>

        {assessment.annotated_file && (
          <button
            className="download-annotated-btn"
            onClick={handleDownload}
            data-testid="download-annotated"
          >
            <Download size={18} />
            Download Annotated Document
          </button>
        )}

        <div className="modal-section">
          <h3>Overall Feedback</h3>
          <p className="overall-feedback">{assessment.overall_feedback}</p>
        </div>

        {assessment.strengths?.length > 0 && (
          <div className="modal-section">
            <h3><TrendingUp size={18} /> Strengths</h3>
            <ul className="feedback-list strengths">
              {assessment.strengths.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </div>
        )}

        {assessment.areas_for_improvement?.length > 0 && (
          <div className="modal-section">
            <h3><Target size={18} /> Areas for Improvement</h3>
            <ul className="feedback-list improvements">
              {assessment.areas_for_improvement.map((a, i) => (
                <li key={i}>{a}</li>
              ))}
            </ul>
          </div>
        )}

        {assessment.criteria_scores && Object.keys(assessment.criteria_scores).length > 0 && (
          <div className="modal-section">
            <h3>Criteria Breakdown</h3>
            <div className="criteria-breakdown">
              {Object.entries(assessment.criteria_scores).map(([name, data]) => (
                <div key={name} className="criterion-score">
                  <div className="criterion-header">
                    <span className="criterion-name">{name}</span>
                    <span className="criterion-value">{data.score?.toFixed(1)} ({data.level})</span>
                  </div>
                  <p className="criterion-feedback">{data.feedback}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {assessment.annotations?.length > 0 && (
          <div className="modal-section">
            <h3>Annotations</h3>
            <div className="annotations-list">
              {assessment.annotations.map((ann, i) => (
                <div key={i} className={`annotation annotation-${ann.type}`}>
                  <span className="annotation-type">{ann.type}</span>
                  <p className="annotation-comment">{ann.comment}</p>
                  {ann.quote && (
                    <blockquote className="annotation-quote">"{ann.quote}"</blockquote>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Job status card
function JobCard({ job, onDownload, onUploadToEfundi, onViewDetails }) {
  const [showLogs, setShowLogs] = useState(false);

  const statusIcons = {
    starting: <RefreshCw size={18} className="spin" />,
    downloading: <RefreshCw size={18} className="spin" />,
    navigating: <RefreshCw size={18} className="spin" />,
    finding_download: <RefreshCw size={18} className="spin" />,
    selecting_options: <RefreshCw size={18} className="spin" />,
    downloading_zip: <RefreshCw size={18} className="spin" />,
    processing: <RefreshCw size={18} className="spin" />,
    completed: <CheckCircle size={18} />,
    failed: <AlertCircle size={18} />
  };

  const statusLabels = {
    starting: 'Starting...',
    downloading: 'Downloading from eFundi...',
    navigating: 'Navigating to assignment...',
    finding_download: 'Finding Download All...',
    selecting_options: 'Selecting options...',
    downloading_zip: 'Downloading ZIP file...',
    processing: 'Processing submissions...',
    completed: 'Completed',
    failed: 'Failed'
  };

  // Calculate stats from assessments (guard against empty arrays)
  const stats = job.results?.assessments?.length > 0 ? {
    count: job.results.assessments.length,
    avgScore: job.results.assessments.reduce((sum, a) => sum + (a.percentage || 0), 0) / job.results.assessments.length,
    minScore: Math.min(...job.results.assessments.map(a => a.percentage || 0)),
    maxScore: Math.max(...job.results.assessments.map(a => a.percentage || 0))
  } : null;

  return (
    <div className={`job-card job-${job.status}`} data-testid={`job-${job.job_id}`}>
      <div className="job-header">
        {statusIcons[job.status] || <Clock size={18} />}
        <span className="job-id">{job.job_id}</span>
        <span className={`job-status status-${job.status}`}>
          {statusLabels[job.status] || job.status}
        </span>
      </div>
      <div className="job-body">
        <span className="job-rubric">Rubric: {job.rubric_name}</span>
        {job.zip_file && <span className="job-file">File: {job.zip_file.split('/').pop()}</span>}
        {job.assignment_url && (
          <span className="job-url">
            <Link size={12} /> eFundi Assignment
          </span>
        )}
        {job.results && (
          <span className="job-count">{job.results.submissions_processed} submissions processed</span>
        )}
        {stats && (
          <div className="job-stats">
            <span className="stat">Avg: {stats.avgScore.toFixed(0)}%</span>
            <span className="stat">Range: {stats.minScore.toFixed(0)}%-{stats.maxScore.toFixed(0)}%</span>
          </div>
        )}
      </div>

      {/* Progress during processing */}
      {job.status === 'processing' && job.results?.assessments && (
        <div className="job-progress">
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${(job.results.assessments.length / (job.results.total_submissions || 15)) * 100}%` }}
            />
          </div>
          <span className="progress-text">
            {job.results.assessments.length} of {job.results.total_submissions || '?'} processed
          </span>
        </div>
      )}

      {/* Logs toggle */}
      {job.logs && job.logs.length > 0 && (
        <div className="job-logs-section">
          <button
            className="toggle-logs-btn"
            onClick={() => setShowLogs(!showLogs)}
          >
            {showLogs ? 'Hide Logs' : 'Show Logs'} ({job.logs.length})
          </button>
          {showLogs && (
            <div className="job-logs">
              {job.logs.map((log, i) => (
                <div key={i} className="log-entry">
                  <span className="log-time">{new Date(log.time).toLocaleTimeString()}</span>
                  <span className="log-message">{log.message}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {job.status === 'completed' && (
        <div className="job-actions">
          <button
            className="view-details-btn"
            onClick={() => onViewDetails(job)}
            data-testid={`view-details-${job.job_id}`}
          >
            <Eye size={16} />
            View Results
          </button>
          <button
            className="download-btn"
            onClick={() => onDownload(job.job_id)}
            data-testid={`download-${job.job_id}`}
          >
            <Download size={16} />
            Download ZIP
          </button>
          {job.assignment_url && onUploadToEfundi && (
            <button
              className="upload-efundi-btn"
              onClick={() => onUploadToEfundi(job.job_id)}
              data-testid={`upload-efundi-${job.job_id}`}
            >
              <Upload size={16} />
              Upload to eFundi
            </button>
          )}
        </div>
      )}
      {job.error && (
        <div className="job-error">
          <AlertCircle size={14} />
          {job.error}
        </div>
      )}
    </div>
  );
}

// Exam Builder Tab Component
function ExamBuilderTab({ showToast }) {
  const [moduleCode, setModuleCode] = useState('HISE411');
  const [moduleName, setModuleName] = useState('HISTORY SNR & FET 4A');
  const [sourceTopics, setSourceTopics] = useState(['', '']);
  const [methodologyTopic, setMethodologyTopic] = useState('');
  const [essayTopic, setEssayTopic] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedExam, setGeneratedExam] = useState(null);
  const [generationProgress, setGenerationProgress] = useState('');
  const [recentExams, setRecentExams] = useState([]);

  // Load recent exams
  useEffect(() => {
    const loadExams = async () => {
      try {
        const res = await fetch(`${API_URL}/api/exams`);
        if (res.ok) {
          const data = await res.json();
          setRecentExams(data.exams || []);
        }
      } catch (error) {
        console.error('Failed to load exams:', error);
      }
    };
    loadExams();
  }, [generatedExam]);

  const handleSourceTopicChange = (index, value) => {
    const newTopics = [...sourceTopics];
    newTopics[index] = value;
    setSourceTopics(newTopics);
  };

  const handleGenerateExam = async () => {
    // Validation
    if (!sourceTopics[0] || !sourceTopics[1]) {
      showToast('Please enter both source-based question topics', 'error');
      return;
    }
    if (!methodologyTopic) {
      showToast('Please enter a methodology question topic', 'error');
      return;
    }
    if (!essayTopic) {
      showToast('Please enter an essay question topic', 'error');
      return;
    }

    setIsGenerating(true);
    setGenerationProgress('Starting exam generation...');
    setGeneratedExam(null);

    try {
      setGenerationProgress('Generating source-based questions with historical sources...');

      const response = await fetch(`${API_URL}/api/exams/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          module_code: moduleCode,
          module_name: moduleName,
          topics: sourceTopics.filter(t => t.trim()),
          methodology_topic: methodologyTopic,
          essay_topic: essayTopic,
          total_marks: 125,
          duration_hours: 3
        })
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || 'Failed to generate exam');
      }

      const data = await response.json();
      setGeneratedExam(data.exam);
      setGenerationProgress('');
      showToast('Exam generated successfully!', 'success');

    } catch (error) {
      console.error('Exam generation error:', error);
      showToast(`Generation failed: ${error.message}`, 'error');
      setGenerationProgress('');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDownloadExam = (filename) => {
    window.open(`${API_URL}/api/exams/download/${filename}`, '_blank');
  };

  // Predefined topic suggestions
  const topicSuggestions = {
    source: [
      'The Cuban Missile Crisis (1962)',
      'The Division of Germany (1945-1949)',
      'The Korean War (1950-1953)',
      'The Berlin Wall and Its Fall',
      'The Vietnam War and Media',
      'The Cold War Origins',
      'Apartheid in South Africa',
      'The Civil Rights Movement',
      'World War II: The Holocaust',
      'Decolonization in Africa'
    ],
    methodology: [
      'The Berlin Airlift',
      'The Cuban Missile Crisis',
      'The Civil Rights Movement',
      'Apartheid Resistance',
      'World War I Causes',
      'The French Revolution'
    ],
    essay: [
      'The role of media in shaping public opinion during the Vietnam War',
      'Evaluate Gorbachev\'s role in the collapse of the Soviet Union',
      'The impact of the Cold War on global politics',
      'Assess the effectiveness of passive resistance in achieving political change',
      'The causes and consequences of World War I',
      'The legacy of colonialism in Africa'
    ]
  };

  return (
    <div className="tab-content" data-testid="exam-builder-tab">
      <section className="section">
        <h2 className="section-title">
          <PenTool size={22} />
          History Exam Builder
        </h2>
        <p className="section-description">
          Generate a complete 125-mark History exam paper with source-based questions, methodology, and essay sections.
          The AI will source legitimate historical materials and create academically rigorous questions.
        </p>

        <div className="exam-builder-form">
          {/* Module Info */}
          <div className="form-section">
            <h3 className="form-section-title">Module Information</h3>
            <div className="form-row">
              <div className="form-group">
                <label>Module Code</label>
                <input
                  type="text"
                  value={moduleCode}
                  onChange={(e) => setModuleCode(e.target.value)}
                  placeholder="e.g., HISE411"
                  className="form-input"
                  data-testid="module-code"
                />
              </div>
              <div className="form-group">
                <label>Module Name</label>
                <input
                  type="text"
                  value={moduleName}
                  onChange={(e) => setModuleName(e.target.value)}
                  placeholder="e.g., HISTORY SNR & FET 4A"
                  className="form-input"
                  data-testid="module-name"
                />
              </div>
            </div>
          </div>

          {/* Source-Based Questions (2 x 25 marks) */}
          <div className="form-section">
            <h3 className="form-section-title">
              <FileText size={18} />
              Section 1: Source-Based Questions (2 × 25 marks = 50 marks)
            </h3>
            <p className="form-hint">
              Enter two topics. The AI will generate historical sources (speeches, cartoons, documents) and questions for each.
            </p>

            {sourceTopics.map((topic, index) => (
              <div key={index} className="topic-input-group">
                <label>Question {index + 1} Topic</label>
                <input
                  type="text"
                  value={topic}
                  onChange={(e) => handleSourceTopicChange(index, e.target.value)}
                  placeholder={`e.g., ${topicSuggestions.source[index]}`}
                  className="form-input"
                  data-testid={`source-topic-${index + 1}`}
                />
                <div className="topic-suggestions">
                  <span className="suggestions-label">Suggestions:</span>
                  {topicSuggestions.source.slice(0, 5).map((s, i) => (
                    <button
                      key={i}
                      type="button"
                      className="suggestion-chip"
                      onClick={() => handleSourceTopicChange(index, s)}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* Methodology Question (25 marks) */}
          <div className="form-section">
            <h3 className="form-section-title">
              <Target size={18} />
              Section 2: Methodology Question (25 marks)
            </h3>
            <p className="form-hint">
              A lesson planning question for trainee teachers. Students will create a teaching resource.
            </p>

            <div className="topic-input-group">
              <label>Methodology Topic</label>
              <input
                type="text"
                value={methodologyTopic}
                onChange={(e) => setMethodologyTopic(e.target.value)}
                placeholder={`e.g., ${topicSuggestions.methodology[0]}`}
                className="form-input"
                data-testid="methodology-topic"
              />
              <div className="topic-suggestions">
                <span className="suggestions-label">Suggestions:</span>
                {topicSuggestions.methodology.map((s, i) => (
                  <button
                    key={i}
                    type="button"
                    className="suggestion-chip"
                    onClick={() => setMethodologyTopic(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Essay Question (50 marks) */}
          <div className="form-section">
            <h3 className="form-section-title">
              <BookOpen size={18} />
              Section 3: Essay Question (50 marks)
            </h3>
            <p className="form-hint">
              A comprehensive essay question with an assessment matrix. The AI will generate the question and marking rubric.
            </p>

            <div className="topic-input-group">
              <label>Essay Topic</label>
              <input
                type="text"
                value={essayTopic}
                onChange={(e) => setEssayTopic(e.target.value)}
                placeholder={`e.g., ${topicSuggestions.essay[0]}`}
                className="form-input"
                data-testid="essay-topic"
              />
              <div className="topic-suggestions">
                <span className="suggestions-label">Suggestions:</span>
                {topicSuggestions.essay.slice(0, 4).map((s, i) => (
                  <button
                    key={i}
                    type="button"
                    className="suggestion-chip"
                    onClick={() => setEssayTopic(s)}
                  >
                    {s.substring(0, 50)}...
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Generate Button */}
          <div className="generate-section">
            <button
              className="generate-btn"
              onClick={handleGenerateExam}
              disabled={isGenerating}
              data-testid="generate-exam-btn"
            >
              {isGenerating ? (
                <>
                  <Loader size={20} className="spin" />
                  Generating Exam...
                </>
              ) : (
                <>
                  <Zap size={20} />
                  Generate 125-Mark Exam Paper
                </>
              )}
            </button>

            {generationProgress && (
              <div className="generation-progress">
                <Loader size={16} className="spin" />
                <span>{generationProgress}</span>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Generated Exam Preview */}
      {generatedExam && (
        <section className="section exam-preview-section">
          <h2 className="section-title">
            <FileCheck size={22} />
            Generated Exam Set
          </h2>

          <div className="exam-set-container">
            {/* First Opportunity */}
            {generatedExam.first_opportunity && (
              <div className="exam-preview-card opportunity-card">
                <div className="opportunity-badge first-opp">1st Opportunity</div>
                <div className="exam-preview-header">
                  <div>
                    <h3>{generatedExam.module_code}: {generatedExam.module_name}</h3>
                    <p>Total: {generatedExam.calculated_total || generatedExam.total_marks} marks | Duration: {generatedExam.duration_hours} hours</p>
                  </div>
                  <div className="exam-download-buttons">
                    <button
                      className="download-exam-btn"
                      onClick={() => handleDownloadExam(generatedExam.first_opportunity.filename)}
                      data-testid="download-1st-exam"
                    >
                      <Download size={18} />
                      Exam
                    </button>
                    <button
                      className="download-memo-btn"
                      onClick={() => handleDownloadExam(generatedExam.first_opportunity.memo_filename)}
                      data-testid="download-1st-memo"
                    >
                      <FileCheck size={18} />
                      Memo
                    </button>
                  </div>
                </div>
                <div className="exam-sections-preview compact">
                  {generatedExam.first_opportunity.source_questions?.map((sq, i) => (
                    <div key={i} className="exam-section-mini">
                      <span className="section-label">Q{i + 1}:</span>
                      <span>{sq.topic}</span>
                      <span className="source-count-mini">{sq.sources?.length} sources</span>
                    </div>
                  ))}
                  <div className="exam-section-mini">
                    <span className="section-label">Q3:</span>
                    <span>Methodology - {generatedExam.first_opportunity.methodology_question?.topic}</span>
                  </div>
                  <div className="exam-section-mini">
                    <span className="section-label">Q4:</span>
                    <span>Essay - {generatedExam.first_opportunity.essay_question?.question?.substring(0, 60)}...</span>
                  </div>
                </div>
              </div>
            )}

            {/* Second Opportunity */}
            {generatedExam.second_opportunity && (
              <div className="exam-preview-card opportunity-card">
                <div className="opportunity-badge second-opp">2nd Opportunity</div>
                <div className="exam-preview-header">
                  <div>
                    <h3>{generatedExam.module_code}: {generatedExam.module_name}</h3>
                    <p>Total: {generatedExam.calculated_total || generatedExam.total_marks} marks | Duration: {generatedExam.duration_hours} hours</p>
                  </div>
                  <div className="exam-download-buttons">
                    <button
                      className="download-exam-btn second"
                      onClick={() => handleDownloadExam(generatedExam.second_opportunity.filename)}
                      data-testid="download-2nd-exam"
                    >
                      <Download size={18} />
                      Exam
                    </button>
                    <button
                      className="download-memo-btn second"
                      onClick={() => handleDownloadExam(generatedExam.second_opportunity.memo_filename)}
                      data-testid="download-2nd-memo"
                    >
                      <FileCheck size={18} />
                      Memo
                    </button>
                  </div>
                </div>
                <div className="exam-sections-preview compact">
                  {generatedExam.second_opportunity.source_questions?.map((sq, i) => (
                    <div key={i} className="exam-section-mini">
                      <span className="section-label">Q{i + 1}:</span>
                      <span>{sq.topic}</span>
                      <span className="source-count-mini">{sq.sources?.length} sources</span>
                    </div>
                  ))}
                  <div className="exam-section-mini">
                    <span className="section-label">Q3:</span>
                    <span>Methodology - {generatedExam.second_opportunity.methodology_question?.topic}</span>
                  </div>
                  <div className="exam-section-mini">
                    <span className="section-label">Q4:</span>
                    <span>Essay - {generatedExam.second_opportunity.essay_question?.question?.substring(0, 60)}...</span>
                  </div>
                </div>
              </div>
            )}

            {/* Fallback for legacy format (single exam) */}
            {!generatedExam.first_opportunity && generatedExam.filename && (
              <div className="exam-preview-card">
                <div className="exam-preview-header">
                  <div>
                    <h3>{generatedExam.module_code}: {generatedExam.module_name}</h3>
                    <p>Total: {generatedExam.calculated_total || generatedExam.total_marks} marks</p>
                  </div>
                  <div className="exam-download-buttons">
                    <button
                      className="download-exam-btn"
                      onClick={() => handleDownloadExam(generatedExam.filename)}
                    >
                      <Download size={18} />
                      Exam
                    </button>
                    {generatedExam.memo_filename && (
                      <button
                        className="download-memo-btn"
                        onClick={() => handleDownloadExam(generatedExam.memo_filename)}
                      >
                        <FileCheck size={18} />
                        Memo
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </section>
      )}

      {/* Recent Exams */}
      {recentExams.length > 0 && (
        <section className="section">
          <h2 className="section-title">
            <Clock size={22} />
            Recent Exam Sets
          </h2>
          <div className="recent-exams-list">
            {recentExams.slice(0, 5).map((exam, i) => (
              <div key={exam._id || i} className="recent-exam-card expanded">
                <div className="recent-exam-info">
                  <span className="exam-code">{exam.module_code}</span>
                  <span className="exam-date">{new Date(exam.created_at).toLocaleDateString()}</span>
                  <span className="exam-marks">{exam.calculated_total || exam.total_marks} marks</span>
                </div>
                <div className="recent-exam-downloads">
                  {/* New format with both opportunities */}
                  {exam.first_opportunity ? (
                    <>
                      <div className="opp-download-group">
                        <span className="opp-label">1st:</span>
                        <button
                          className="download-btn-small"
                          onClick={() => handleDownloadExam(exam.first_opportunity.filename)}
                          title="1st Opportunity Exam"
                        >
                          <Download size={14} />
                        </button>
                        <button
                          className="download-btn-small memo-btn"
                          onClick={() => handleDownloadExam(exam.first_opportunity.memo_filename)}
                          title="1st Opportunity Memo"
                        >
                          <FileCheck size={14} />
                        </button>
                      </div>
                      <div className="opp-download-group">
                        <span className="opp-label">2nd:</span>
                        <button
                          className="download-btn-small second"
                          onClick={() => handleDownloadExam(exam.second_opportunity.filename)}
                          title="2nd Opportunity Exam"
                        >
                          <Download size={14} />
                        </button>
                        <button
                          className="download-btn-small memo-btn second"
                          onClick={() => handleDownloadExam(exam.second_opportunity.memo_filename)}
                          title="2nd Opportunity Memo"
                        >
                          <FileCheck size={14} />
                        </button>
                      </div>
                    </>
                  ) : (
                    /* Legacy format */
                    <div className="recent-exam-actions">
                      <button
                        className="download-btn-small"
                        onClick={() => handleDownloadExam(exam.filename)}
                        title="Download Exam Paper"
                      >
                        <Download size={14} />
                      </button>
                      {exam.memo_filename && (
                        <button
                          className="download-btn-small memo-btn"
                          onClick={() => handleDownloadExam(exam.memo_filename)}
                          title="Download Memorandum"
                        >
                          <FileCheck size={14} />
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

// Main App
function App() {
  const [activeTab, setActiveTab] = useState('assess');
  const [rubrics, setRubrics] = useState([]);
  const [selectedRubric, setSelectedRubric] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [recentAssessments, setRecentAssessments] = useState([]);
  const [toasts, setToasts] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedAssessment, setSelectedAssessment] = useState(null);

  // Live progress state
  const [liveJob, setLiveJob] = useState(null);
  const [liveProgress, setLiveProgress] = useState(null);

  // eFundi state
  const [efundiAuth, setEfundiAuth] = useState(null);
  const [efundiUsername, setEfundiUsername] = useState('');
  const [efundiPassword, setEfundiPassword] = useState('');
  const [assignmentUrl, setAssignmentUrl] = useState('');
  const [assignmentName, setAssignmentName] = useState('');

  // Assignment instructions state
  const [assignmentInstructions, setAssignmentInstructions] = useState('');
  const [instructionsFile, setInstructionsFile] = useState(null);

  // Toast helpers
  const showToast = (message, type = 'info') => {
    const id = `${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    setToasts(prev => [...prev, { id, message, type }]);
  };

  const removeToast = (id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  };

  // Load data
  const loadRubrics = useCallback(async () => {
    try {
      const data = await api.get('/api/rubrics');
      setRubrics(data.rubrics || []);
    } catch (error) {
      console.error('Failed to load rubrics:', error);
    }
  }, []);

  const loadJobs = useCallback(async () => {
    try {
      const data = await api.get('/api/jobs');
      setJobs(data.jobs || []);
    } catch (error) {
      console.error('Failed to load jobs:', error);
    }
  }, []);

  const loadAssessments = useCallback(async () => {
    try {
      const data = await api.get('/api/assessments');
      setRecentAssessments(data.assessments || []);
    } catch (error) {
      console.error('Failed to load assessments:', error);
    }
  }, []);

  const checkEfundiAuth = useCallback(async () => {
    try {
      const data = await api.get('/api/efundi/status');
      setEfundiAuth(data);
    } catch (error) {
      console.error('Failed to check eFundi status:', error);
    }
  }, []);

  useEffect(() => {
    loadRubrics();
    loadJobs();
    loadAssessments();
    checkEfundiAuth();

    // Poll jobs every 5 seconds
    const interval = setInterval(loadJobs, 5000);
    return () => clearInterval(interval);
  }, [loadRubrics, loadJobs, loadAssessments, checkEfundiAuth]);

  // Upload rubric
  const handleRubricUpload = async (file) => {
    setIsLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('name', file.name.replace(/\.[^.]+$/, ''));

      const result = await api.post('/api/rubric/upload', formData, true);
      showToast(`Rubric "${result.rubric.name}" uploaded successfully!`, 'success');
      loadRubrics();
    } catch (error) {
      showToast(`Failed to upload rubric: ${error.message}`, 'error');
    } finally {
      setIsLoading(false);
    }
  };

  // Create default essay rubric
  const handleCreateDefaultRubric = async () => {
    setIsLoading(true);
    try {
      const formData = new FormData();
      formData.append('name', 'Essay Assessment Rubric (50 marks)');
      formData.append('total_marks', '50');

      const result = await api.post('/api/rubric/essay-default', formData, true);
      showToast(`Default rubric "${result.rubric.name}" created!`, 'success');
      loadRubrics();
    } catch (error) {
      showToast(`Failed to create rubric: ${error.message}`, 'error');
    } finally {
      setIsLoading(false);
    }
  };

  // eFundi authentication
  const handleEfundiAuth = async (e) => {
    e.preventDefault();
    if (!efundiUsername || !efundiPassword) {
      showToast('Please enter username and password', 'error');
      return;
    }

    setIsLoading(true);
    try {
      const result = await api.post('/api/efundi/authenticate', {
        username: efundiUsername,
        password: efundiPassword
      });
      showToast(result.message, 'success');
      setEfundiPassword('');
      checkEfundiAuth();
    } catch (error) {
      showToast(`Authentication failed: ${error.message}`, 'error');
    } finally {
      setIsLoading(false);
    }
  };

  // eFundi automated download and assess
  const handleEfundiAutomate = async () => {
    if (!selectedRubric) {
      showToast('Please select a rubric first', 'error');
      return;
    }
    if (!assignmentUrl) {
      showToast('Please enter the eFundi assignment URL', 'error');
      return;
    }

    setIsLoading(true);
    try {
      const result = await api.post('/api/efundi/download-and-assess', {
        assignment_url: assignmentUrl,
        rubric_id: selectedRubric._id,
        assignment_name: assignmentName || null
      });
      showToast(`Job started: ${result.job_id}`, 'success');
      setActiveTab('jobs');
      loadJobs();
    } catch (error) {
      showToast(`Failed: ${error.message}`, 'error');
    } finally {
      setIsLoading(false);
    }
  };

  // Upload results to eFundi
  const handleUploadToEfundi = async (jobId) => {
    setIsLoading(true);
    try {
      const result = await api.post(`/api/efundi/upload-results/${jobId}`, {});
      showToast(result.message, 'success');
    } catch (error) {
      showToast(`Upload failed: ${error.message}`, 'error');
    } finally {
      setIsLoading(false);
    }
  };

  // Single assessment
  const handleSingleAssessment = async (file) => {
    if (!selectedRubric) {
      showToast('Please select a rubric first', 'error');
      return;
    }

    setIsLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('rubric_id', selectedRubric._id);

      // Add instructions if provided
      if (assignmentInstructions) {
        formData.append('instructions', assignmentInstructions);
      }
      if (instructionsFile) {
        formData.append('instructions_file', instructionsFile);
      }

      const result = await api.post('/api/assess/single', formData, true);
      showToast(`Assessment complete! Score: ${result.total_score?.toFixed(1)}/${result.max_score}`, 'success');
      setSelectedAssessment(result);
      loadAssessments();
    } catch (error) {
      showToast(`Assessment failed: ${error.message}`, 'error');
    } finally {
      setIsLoading(false);
    }
  };

  // Bulk assessment
  const handleBulkAssessment = async (file) => {
    if (!selectedRubric) {
      showToast('Please select a rubric first', 'error');
      return;
    }

    setIsLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('rubric_id', selectedRubric._id);

      // Add instructions if provided
      if (assignmentInstructions) {
        formData.append('instructions', assignmentInstructions);
      }
      if (instructionsFile) {
        formData.append('instructions_file', instructionsFile);
      }

      const result = await api.post('/api/assess/bulk', formData, true);
      showToast(`Bulk assessment started! Job ID: ${result.job_id}`, 'success');

      // Start live monitoring
      setLiveJob(result.job_id);
      setLiveProgress({ status: 'starting', progress: 0, total: 0 });

      // Poll for updates
      const pollInterval = setInterval(async () => {
        try {
          const jobData = await api.get(`/api/job/${result.job_id}`);
          setLiveProgress(jobData);

          if (jobData.status === 'completed' || jobData.status === 'failed') {
            clearInterval(pollInterval);
            setLiveJob(null);
            setLiveProgress(null);
            loadJobs();

            if (jobData.status === 'completed') {
              showToast(`Assessment complete! ${jobData.results?.submissions_processed || 0} submissions processed.`, 'success');
              setActiveTab('jobs');
            } else {
              showToast(`Assessment failed: ${jobData.error}`, 'error');
            }
          }
        } catch (e) {
          console.error('Poll error:', e);
        }
      }, 2000);

    } catch (error) {
      if (error.message === 'Failed to fetch') {
        showToast('Upload failed: Network error. Please check your connection and try again. If uploading a large file, it may have timed out.', 'error');
      } else {
        showToast(`Failed to start assessment: ${error.message}`, 'error');
      }
    } finally {
      setIsLoading(false);
    }
  };

  // Download results - using fetch + blob for reliability
  const handleDownload = async (jobId) => {
    try {
      showToast('Starting download...', 'info');
      const response = await fetch(`${API_URL}/api/download/${jobId}`);
      if (!response.ok) throw new Error('Download failed');

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `efundi_graded_${jobId}.zip`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      showToast('Download complete!', 'success');
    } catch (error) {
      showToast(`Download failed: ${error.message}`, 'error');
    }
  };

  // View job results with per-student breakdown
  const [selectedJob, setSelectedJob] = useState(null);

  const handleViewJobDetails = (job) => {
    setSelectedJob(job);
  };

  // View assessment details
  const handleViewDetails = async (assessment) => {
    try {
      if (assessment._id) {
        const detailed = await api.get(`/api/assessment/${assessment._id}`);
        setSelectedAssessment(detailed);
      } else {
        setSelectedAssessment(assessment);
      }
    } catch (error) {
      setSelectedAssessment(assessment);
    }
  };

  return (
    <div className="app" data-testid="smart-assessor-app">
      {/* Toast container */}
      <div className="toast-container">
        {toasts.map(toast => (
          <Toast
            key={toast.id}
            message={toast.message}
            type={toast.type}
            onClose={() => removeToast(toast.id)}
          />
        ))}
      </div>

      {/* Header */}
      <header className="header">
        <div className="header-content">
          <div className="logo">
            <Zap size={28} className="logo-icon" />
            <span className="logo-text">Smart Assessor</span>
          </div>
          <p className="tagline">AI-Powered Assignment Grading</p>
        </div>
      </header>

      {/* Navigation */}
      <nav className="nav">
        <button
          className={`nav-btn ${activeTab === 'assess' ? 'nav-btn-active' : ''}`}
          onClick={() => setActiveTab('assess')}
          data-testid="nav-assess"
        >
          <FileText size={18} />
          Assess
        </button>
        <button
          className={`nav-btn ${activeTab === 'exam-builder' ? 'nav-btn-active' : ''}`}
          onClick={() => setActiveTab('exam-builder')}
          data-testid="nav-exam-builder"
        >
          <PenTool size={18} />
          Exam Builder
        </button>
        <button
          className={`nav-btn ${activeTab === 'rubrics' ? 'nav-btn-active' : ''}`}
          onClick={() => setActiveTab('rubrics')}
          data-testid="nav-rubrics"
        >
          <BookOpen size={18} />
          Rubrics
        </button>
        <button
          className={`nav-btn ${activeTab === 'jobs' ? 'nav-btn-active' : ''}`}
          onClick={() => setActiveTab('jobs')}
          data-testid="nav-jobs"
        >
          <Clock size={18} />
          Jobs
        </button>
      </nav>

      {/* Main content */}
      <main className="main">
        {/* Assess Tab */}
        {activeTab === 'assess' && (
          <div className="tab-content" data-testid="assess-tab">
            <section className="section">
              <h2 className="section-title">
                <Target size={22} />
                Select Rubric
              </h2>
              {rubrics.length === 0 ? (
                <div className="empty-state">
                  <BookOpen size={48} />
                  <p>No rubrics available. Upload one in the Rubrics tab.</p>
                </div>
              ) : (
                <div className="rubrics-grid">
                  {rubrics.map(rubric => (
                    <RubricCard
                      key={rubric._id}
                      rubric={rubric}
                      isSelected={selectedRubric?._id === rubric._id}
                      onSelect={setSelectedRubric}
                    />
                  ))}
                </div>
              )}
            </section>

            {/* Assignment Instructions Section */}
            <section className="section instructions-section">
              <h2 className="section-title">
                <FileText size={22} />
                Assignment Instructions
              </h2>
              <p className="section-description">
                Provide the assignment task/instructions so the AI knows what students were supposed to do.
              </p>

              <div className="instructions-container">
                <div className="instructions-upload">
                  <FileDropzone
                    onFileSelect={(file) => {
                      setInstructionsFile(file);
                      // Read file content
                      const reader = new FileReader();
                      reader.onload = (e) => {
                        if (file.name.endsWith('.txt')) {
                          setAssignmentInstructions(e.target.result);
                        }
                      };
                      if (file.name.endsWith('.txt')) {
                        reader.readAsText(file);
                      }
                      showToast(`Instructions file loaded: ${file.name}`, 'success');
                    }}
                    accept=".docx,.pdf,.txt"
                    label="Upload Instructions (DOCX/PDF/TXT)"
                    icon={FileText}
                  />
                  {instructionsFile && (
                    <div className="file-loaded-badge">
                      <CheckCircle size={16} />
                      <span>{instructionsFile.name}</span>
                      <button
                        className="clear-btn"
                        onClick={() => { setInstructionsFile(null); setAssignmentInstructions(''); }}
                      >
                        <X size={14} />
                      </button>
                    </div>
                  )}
                </div>

                <div className="instructions-divider">
                  <span>OR</span>
                </div>

                <div className="instructions-text">
                  <textarea
                    className="instructions-textarea"
                    placeholder="Paste or type the assignment instructions here...

Example:
Assignment 1: AI Lesson Plan Critique

Task: Critique the attached AI-generated lesson plan and create an improved version.

Part A: Identify at least 3 flaws in the AI lesson plan
Part B: Create an improved lesson plan addressing these issues
Part C: Reflect on how your improvements enhance historical thinking skills"
                    value={assignmentInstructions}
                    onChange={(e) => setAssignmentInstructions(e.target.value)}
                    rows={8}
                    data-testid="assignment-instructions"
                  />
                </div>
              </div>

              {assignmentInstructions && (
                <div className="instructions-preview">
                  <h4>Instructions Preview:</h4>
                  <p>{assignmentInstructions.substring(0, 300)}...</p>
                </div>
              )}
            </section>

            {/* eFundi Automation Section */}
            <section className="section efundi-section">
              <h2 className="section-title">
                <Globe size={22} />
                eFundi Automation
              </h2>

              <div className="efundi-container">
                {/* Authentication Status */}
                <div className="efundi-auth-status">
                  {efundiAuth?.authenticated ? (
                    <div className="auth-badge auth-success">
                      <CheckCircle size={18} />
                      <span>Connected as {efundiAuth.username}</span>
                    </div>
                  ) : (
                    <div className="auth-badge auth-pending">
                      <Lock size={18} />
                      <span>Not authenticated</span>
                    </div>
                  )}
                </div>

                {/* Login Form */}
                {!efundiAuth?.authenticated && (
                  <form className="efundi-login-form" onSubmit={handleEfundiAuth}>
                    <div className="form-row">
                      <input
                        type="text"
                        placeholder="eFundi Username"
                        value={efundiUsername}
                        onChange={(e) => setEfundiUsername(e.target.value)}
                        className="form-input"
                        data-testid="efundi-username"
                      />
                      <input
                        type="password"
                        placeholder="eFundi Password"
                        value={efundiPassword}
                        onChange={(e) => setEfundiPassword(e.target.value)}
                        className="form-input"
                        data-testid="efundi-password"
                      />
                      <button type="submit" className="auth-btn" data-testid="efundi-login">
                        <Lock size={16} />
                        Authenticate
                      </button>
                    </div>
                  </form>
                )}

                {/* Assignment URL Input */}
                {efundiAuth?.authenticated && (
                  <div className="efundi-automate">
                    <div className="url-input-row">
                      <Link size={18} className="url-icon" />
                      <input
                        type="text"
                        placeholder="Paste eFundi Site URL (e.g., https://efundi.nwu.ac.za/portal/site/...)"
                        value={assignmentUrl}
                        onChange={(e) => setAssignmentUrl(e.target.value)}
                        className="form-input url-input"
                        data-testid="assignment-url"
                      />
                    </div>
                    <div className="url-input-row">
                      <FileText size={18} className="url-icon" />
                      <input
                        type="text"
                        placeholder="Assignment Name (optional - to find specific assignment)"
                        value={assignmentName}
                        onChange={(e) => setAssignmentName(e.target.value)}
                        className="form-input url-input"
                        data-testid="assignment-name"
                      />
                    </div>
                    <button
                      className="automate-btn"
                      onClick={handleEfundiAutomate}
                      disabled={!selectedRubric || !assignmentUrl}
                      data-testid="start-automation"
                    >
                      <Play size={18} />
                      Download & Assess All Submissions
                    </button>
                    <p className="help-text">
                      This will navigate to eFundi → Assignments → Grade → Download All → Process with AI → Package for upload.
                    </p>
                  </div>
                )}
              </div>
            </section>

            <section className="section">
              <h2 className="section-title">
                <Upload size={22} />
                Manual Upload
              </h2>
              <div className="upload-options">
                <div className="upload-option">
                  <h3>Single Submission</h3>
                  <FileDropzone
                    onFileSelect={handleSingleAssessment}
                    accept=".docx,.pdf,.doc"
                    label="Upload Essay (DOCX/PDF)"
                    icon={FileText}
                  />
                </div>
                <div className="upload-option">
                  <h3>Bulk Assessment (eFundi ZIP)</h3>
                  <FileDropzone
                    onFileSelect={handleBulkAssessment}
                    accept=".zip"
                    label="Upload eFundi ZIP"
                    icon={FileArchive}
                  />
                </div>
              </div>
            </section>

            {recentAssessments.length > 0 && (
              <section className="section">
                <h2 className="section-title">
                  <Award size={22} />
                  Recent Assessments
                </h2>
                <div className="assessments-grid">
                  {recentAssessments.slice(0, 6).map(assessment => (
                    <AssessmentResultCard
                      key={assessment._id}
                      assessment={assessment}
                      onViewDetails={handleViewDetails}
                    />
                  ))}
                </div>
              </section>
            )}
          </div>
        )}

        {/* Exam Builder Tab */}
        {activeTab === 'exam-builder' && (
          <ExamBuilderTab showToast={showToast} />
        )}

        {/* Rubrics Tab */}
        {activeTab === 'rubrics' && (
          <div className="tab-content" data-testid="rubrics-tab">
            <section className="section">
              <h2 className="section-title">
                <Upload size={22} />
                Upload New Rubric
              </h2>
              <div className="rubric-upload-options">
                <FileDropzone
                  onFileSelect={handleRubricUpload}
                  accept=".docx,.pdf,.doc"
                  label="Upload Rubric (DOCX/PDF)"
                  icon={BookOpen}
                />
                <div className="or-divider">OR</div>
                <button
                  className="create-default-btn"
                  onClick={handleCreateDefaultRubric}
                  data-testid="create-default-rubric"
                >
                  <Zap size={18} />
                  Create Default Essay Rubric (50 marks)
                </button>
              </div>
            </section>

            <section className="section">
              <h2 className="section-title">
                <BookOpen size={22} />
                Available Rubrics
              </h2>
              {rubrics.length === 0 ? (
                <div className="empty-state">
                  <BookOpen size={48} />
                  <p>No rubrics uploaded yet.</p>
                </div>
              ) : (
                <div className="rubrics-list">
                  {rubrics.map(rubric => (
                    <RubricDetailCard key={rubric._id} rubric={rubric} />
                  ))}
                </div>
              )}
            </section>
          </div>
        )}

        {/* Jobs Tab */}
        {activeTab === 'jobs' && (
          <div className="tab-content" data-testid="jobs-tab">
            <section className="section">
              <div className="section-header">
                <h2 className="section-title">
                  <Clock size={22} />
                  Assessment Jobs
                </h2>
                <button className="refresh-btn" onClick={loadJobs} data-testid="refresh-jobs">
                  <RefreshCw size={18} />
                  Refresh
                </button>
              </div>
              {jobs.length === 0 ? (
                <div className="empty-state">
                  <Clock size={48} />
                  <p>No assessment jobs yet. Start a bulk assessment to see jobs here.</p>
                </div>
              ) : (
                <div className="jobs-list">
                  {jobs.map(job => (
                    <JobCard
                      key={job.job_id}
                      job={job}
                      onDownload={handleDownload}
                      onUploadToEfundi={handleUploadToEfundi}
                      onViewDetails={handleViewJobDetails}
                    />
                  ))}
                </div>
              )}
            </section>
          </div>
        )}
      </main>

      {/* Loading overlay */}
      {isLoading && (
        <div className="loading-overlay" data-testid="loading-overlay">
          <div className="loading-spinner">
            <RefreshCw size={48} className="spin" />
            <span>Processing...</span>
          </div>
        </div>
      )}

      {/* Assessment details modal */}
      {selectedAssessment && (
        <AssessmentDetailsModal
          assessment={selectedAssessment}
          onClose={() => setSelectedAssessment(null)}
        />
      )}

      {/* Job Results Modal - per-student breakdown */}
      {selectedJob && (
        <JobResultsModal
          job={selectedJob}
          onClose={() => setSelectedJob(null)}
          onDownload={handleDownload}
        />
      )}

      {/* Live Progress Overlay */}
      {liveJob && liveProgress && (
        <LiveProgressOverlay
          jobId={liveJob}
          progress={liveProgress}
          onClose={() => { setLiveJob(null); setLiveProgress(null); }}
        />
      )}
    </div>
  );
}

export default App;
