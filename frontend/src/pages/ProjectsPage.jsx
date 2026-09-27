import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { createProject, getProjects } from '../api/projects';
import EmptyState from '../components/ui/EmptyState';
import ErrorState from '../components/ui/ErrorState';
import LoadingState from '../components/ui/LoadingState';
import PageHeader from '../components/ui/PageHeader';

export default function ProjectsPage() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const loadProjects = async () => {
    setLoading(true);
    setError('');

    try {
      const data = await getProjects();
      setProjects(data);
    } catch (loadError) {
      console.error('Projects load failed:', loadError);
      setError(loadError.message || 'Unable to load projects.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProjects();
  }, []);

  async function handleCreateProject(event) {
    event.preventDefault();

    if (!name.trim()) {
      return;
    }

    setSubmitting(true);

    try {
      const payload = {
        name: name.trim(),
        description: description.trim() || null,
      };
      const newProject = await createProject(payload);
      setProjects((current) => [newProject, ...current]);
      setName('');
      setDescription('');
    } catch (submitError) {
      console.error('Project creation failed:', submitError);
      setError(submitError.message || 'Unable to create project.');
    } finally {
      setSubmitting(false);
    }
  }

  const formAction = (
    <form className="project-form" onSubmit={handleCreateProject}>
      <input
        type="text"
        placeholder="Project name"
        value={name}
        onChange={(event) => setName(event.target.value)}
        aria-label="Project name"
      />
      <input
        type="text"
        placeholder="Description"
        value={description}
        onChange={(event) => setDescription(event.target.value)}
        aria-label="Project description"
      />
      <button type="submit" className="primary-button" disabled={submitting}>
        {submitting ? 'Creating...' : 'Create Project'}
      </button>
    </form>
  );

  return (
    <>
      <PageHeader title="Projects" description="Workspace overview for active project work." action={formAction} />

      {loading ? <LoadingState message="Loading projects..." /> : null}
      {!loading && error ? (
        <ErrorState message={error} onRetry={() => loadProjects()} />
      ) : null}

      {!loading && !error && projects.length === 0 ? (
        <EmptyState title="No projects yet." message="Create a project to begin building your workspace." />
      ) : null}

      {!loading && !error && projects.length > 0 ? (
        <div className="project-grid">
          {projects.map((project) => (
            <Link key={project.id} to={`/projects/${project.id}`} className="project-card">
              <div className="project-card-header">
                <span className="project-pill">Project</span>
                <span className="project-metadata">
                  {new Date(project.updated_at).toLocaleDateString()}
                </span>
              </div>
              <h2>{project.name}</h2>
              {project.description ? <p>{project.description}</p> : <p className="muted">No description yet.</p>}
              {project.objective ? <p className="project-objective">{project.objective}</p> : null}
              <div className="project-meta-row">
                {project.initial_input ? <span>Input captured</span> : null}
                {project.initial_script ? <span>Script captured</span> : null}
              </div>
            </Link>
          ))}
        </div>
      ) : null}
    </>
  );
}
