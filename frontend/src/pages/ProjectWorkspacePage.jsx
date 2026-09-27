import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { getProject } from '../api/projects';
import EmptyState from '../components/ui/EmptyState';
import ErrorState from '../components/ui/ErrorState';
import LoadingState from '../components/ui/LoadingState';
import PageHeader from '../components/ui/PageHeader';

export default function ProjectWorkspacePage() {
  const { projectId } = useParams();
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadProject = async () => {
    setLoading(true);
    setError('');

    try {
      const data = await getProject(projectId);
      setProject(data);
    } catch (loadError) {
      console.error(`Project ${projectId} failed to load:`, loadError);
      setError(loadError.message || 'Unable to load project.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProject();
  }, [projectId]);

  if (loading) {
    return <LoadingState message="Loading project workspace..." />;
  }

  if (error) {
    return <ErrorState message={error} onRetry={loadProject} />;
  }

  if (!project) {
    return <EmptyState title="Project not found." message="The selected project could not be loaded." />;
  }

  return (
    <>
      <PageHeader
        title={project.name}
        description={project.description || 'Project workspace overview.'}
      />

      <section className="workspace-overview card-panel">
        <div className="overview-grid">
          <div>
            <h2>Overview</h2>
            <p>{project.objective || 'No project objective has been set yet.'}</p>
          </div>
          <div className="meta-list">
            <div>
              <span className="meta-label">Created</span>
              <strong>{new Date(project.created_at).toLocaleString()}</strong>
            </div>
            <div>
              <span className="meta-label">Updated</span>
              <strong>{new Date(project.updated_at).toLocaleString()}</strong>
            </div>
            <div>
              <span className="meta-label">Initial input</span>
              <strong>{project.initial_input || 'Not provided'}</strong>
            </div>
          </div>
        </div>
      </section>

      <section className="domain-grid">
        <div className="domain-card card-panel">
          <h3>Parts</h3>
          <p>Not implemented yet</p>
        </div>
        <div className="domain-card card-panel">
          <h3>Sources</h3>
          <p>Not implemented yet</p>
        </div>
        <div className="domain-card card-panel">
          <h3>Findings</h3>
          <p>Not implemented yet</p>
        </div>
        <div className="domain-card card-panel">
          <h3>Assets</h3>
          <p>Not implemented yet</p>
        </div>
        <div className="domain-card card-panel">
          <h3>Scripts</h3>
          <p>Not implemented yet</p>
        </div>
        <div className="domain-card card-panel">
          <h3>History</h3>
          <p>Not implemented yet</p>
        </div>
      </section>
    </>
  );
}
