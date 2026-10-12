import React, { useState } from 'react';
import ImportPanel from './components/ImportPanel';
import TemplatePicker from './components/TemplatePicker';
import DetailsForm from './components/DetailsForm';
import SubmitBar from './components/SubmitBar';
import StatusPanel from './components/StatusPanel';

function getTodayDateString() {
  const d = new Date();
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export default function App() {
  const [recipients, setRecipients] = useState([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState('');
  const [title, setTitle] = useState('');
  const [organizationName, setOrganizationName] = useState('');
  const [issuedDate, setIssuedDate] = useState(getTodayDateString());
  const [outputFormat, setOutputFormat] = useState('pdf');
  const [activeJobId, setActiveJobId] = useState(null);

  const handleReset = () => {
    setActiveJobId(null);
    setRecipients([]);
    setTitle('');
  };

  return (
    <div className="app-container">
      <header className="header-section">
        <h1>🎓 Bulk Certificate Generator</h1>
        <p>
          High-performance, fault-tolerant bulk certificate rendering with multi-format export and live progress tracking.
        </p>
      </header>

      {activeJobId ? (
        <StatusPanel jobId={activeJobId} onReset={handleReset} />
      ) : (
        <>
          <ImportPanel recipients={recipients} setRecipients={setRecipients} />

          <TemplatePicker
            selectedTemplateId={selectedTemplateId}
            setSelectedTemplateId={setSelectedTemplateId}
          />

          <DetailsForm
            title={title}
            setTitle={setTitle}
            organizationName={organizationName}
            setOrganizationName={setOrganizationName}
            issuedDate={issuedDate}
            setIssuedDate={setIssuedDate}
            outputFormat={outputFormat}
            setOutputFormat={setOutputFormat}
          />

          <SubmitBar
            title={title}
            organizationName={organizationName}
            issuedDate={issuedDate}
            selectedTemplateId={selectedTemplateId}
            outputFormat={outputFormat}
            recipients={recipients}
            onJobStarted={(jobId) => setActiveJobId(jobId)}
          />
        </>
      )}
    </div>
  );
}
