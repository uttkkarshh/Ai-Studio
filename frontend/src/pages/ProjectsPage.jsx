import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { sendProjectAiMessage } from '../api/ai';
import { createProject, deleteProject, getProjects, updateProject } from '../api/projects';
import EmptyState from '../components/ui/EmptyState';
import ErrorState from '../components/ui/ErrorState';
import LoadingState from '../components/ui/LoadingState';
import PageHeader from '../components/ui/PageHeader';

export default function ProjectsPage() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [editingProject, setEditingProject] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState('');

  const loadProjects = useCallback(async () => {
    try {
      const data = await getProjects();
      setProjects(data);
      setError('');
    } catch (loadError) {
      console.error('Projects load failed:', loadError);
      setError(loadError.message || 'Unable to load projects.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    getProjects()
      .then((data) => {
        if (active) {
          setProjects(data);
          setError('');
        }
      })
      .catch((loadError) => {
        if (active) setError(loadError.message || 'Unable to load projects.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  async function handleCreateProject(event) {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    setMessage('');

    try {
      const formElement = event.currentTarget;
      const form = new FormData(formElement);
      const payload = {
        name: form.get('name'),
        description: form.get('description') || null,
        objective: form.get('objective') || null,
        initial_input: form.get('initial_input') || null,
        initial_script: form.get('initial_script') || null,
      };
      const createdProject = await createProject(payload);
      let initialAiResponse = null;
      if (payload.initial_input) {
        initialAiResponse = await sendProjectAiMessage(createdProject.id, {
          message: payload.initial_input,
          scope: 'project',
          part_id: null,
          current_proposal: null,
        });
      }
      await loadProjects();
      setMessage('Project created.');
      formElement.reset();
      navigate(`/projects/${createdProject.id}`, { state: { initialAiResponse } });
    } catch (submitError) {
      console.error('Project creation failed:', submitError);
      setError(submitError.message || 'Unable to create project.');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleUpdateProject(event) {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    setMessage('');
    try {
      const form = new FormData(event.currentTarget);
      await updateProject(editingProject.id, {
        name: form.get('name'),
        description: form.get('description') || null,
        objective: form.get('objective') || null,
        initial_input: form.get('initial_input') || null,
        initial_script: form.get('initial_script') || null,
      });
      setEditingProject(null);
      await loadProjects();
      setMessage('Project updated.');
    } catch (submitError) {
      setError(submitError.message || 'Unable to update project.');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDeleteProject(project) {
    if (!window.confirm(`Delete "${project.name}"? This permanently deletes the project and its child records.`)) return;
    setSubmitting(true);
    setError('');
    setMessage('');
    try {
      await deleteProject(project.id);
      await loadProjects();
      setMessage('Project deleted.');
    } catch (deleteError) {
      setError(deleteError.message || 'Unable to delete project.');
    } finally {
      setSubmitting(false);
    }
  }

  const formAction = (
    <form className="project-form" onSubmit={handleCreateProject}>
      <input
        type="text"
        placeholder="Project name"
        name="name"
        required
        aria-label="Project name"
      />
      <input
        type="text"
        placeholder="Description"
        name="description"
        aria-label="Project description"
      />
      <details className="project-extra-fields">
        <summary>Objective and initial content</summary>
        <input type="text" name="objective" placeholder="Objective" aria-label="Project objective" required />
        <textarea name="initial_input" placeholder="Initial input" aria-label="Project initial input" required />
        <textarea name="initial_script" placeholder="Initial script" aria-label="Project initial script" />
      </details>
      <button type="submit" className="primary-button" disabled={submitting}>
        {submitting ? 'Saving...' : 'Create Project'}
      </button>
    </form>
  );

  return (
    <>
      <PageHeader title="Projects" description="Workspace overview for active project work." action={formAction} />

      {loading ? <LoadingState message="Loading projects..." /> : null}
      {message ? <p className="feedback-message" role="status">{message}</p> : null}
      {!loading && error ? (
        <ErrorState message={error} onRetry={() => loadProjects()} />
      ) : null}

      {editingProject ? (
        <form className="card-panel editor-form" onSubmit={handleUpdateProject}>
          <h3>Edit {editingProject.name}</h3>
          <label>Name<input name="name" required defaultValue={editingProject.name} /></label>
          <label>Description<textarea name="description" defaultValue={editingProject.description || ''} /></label>
          <label>Objective<textarea name="objective" defaultValue={editingProject.objective || ''} /></label>
          <label>Initial input<textarea name="initial_input" defaultValue={editingProject.initial_input || ''} /></label>
          <label>Initial script<textarea name="initial_script" defaultValue={editingProject.initial_script || ''} /></label>
          <div className="action-row">
            <button type="submit" className="primary-button" disabled={submitting}>{submitting ? 'Saving...' : 'Save project'}</button>
            <button type="button" className="secondary-button" onClick={() => setEditingProject(null)}>Cancel</button>
          </div>
        </form>
      ) : null}

      {!loading && !error && projects.length === 0 ? (
        <EmptyState title="No projects yet." message="Create a project to begin building your workspace." />
      ) : null}

      {!loading && !error && projects.length > 0 ? (
        <div className="project-grid">
          {projects.map((project) => (
            <article key={project.id} className="project-card">
              <Link to={`/projects/${project.id}`} className="project-card-link">
                <div className="project-card-header">
                  <span className="project-pill">Project</span>
                  <span className="project-metadata">{new Date(project.updated_at).toLocaleDateString()}</span>
                </div>
                <h2>{project.name}</h2>
                {project.description ? <p>{project.description}</p> : <p className="muted">No description yet.</p>}
                {project.objective ? <p className="project-objective">{project.objective}</p> : null}
                <div className="project-meta-row">
                  {project.initial_input ? <span>Input captured</span> : null}
                  {project.initial_script ? <span>Script captured</span> : null}
                </div>
              </Link>
              <div className="action-row">
                <button type="button" className="secondary-button" disabled={submitting} onClick={() => setEditingProject(project)}>Edit</button>
                <button type="button" className="danger-button" disabled={submitting} onClick={() => handleDeleteProject(project)}>Delete</button>
              </div>
              <details className="debug-details"><summary>View raw project JSON</summary><pre>{JSON.stringify(project, null, 2)}</pre></details>
            </article>
          ))}
        </div>
      ) : null}
    </>
  );
}
