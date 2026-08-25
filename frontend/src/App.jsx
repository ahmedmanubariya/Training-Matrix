import { useEffect, useMemo, useState } from 'react'
import { Navigate, NavLink, Route, Routes, useNavigate, useParams } from 'react-router-dom'
import {
  AlertTriangle, BookOpenCheck, CheckCircle2, ClipboardCheck, FileClock, FileSearch,
  Files, Gauge, History, LogOut, Menu, Search, Settings, ShieldCheck, Users, X
} from 'lucide-react'
import { api } from './api'

const roleRank = { user: 1, staff: 1, manager: 2, qa: 3, admin: 4 }

function useAuth() {
  const [user, setUser] = useState(undefined)
  useEffect(() => { api.me().then(r => setUser(r.user)).catch(() => setUser(null)) }, [])
  return [user, setUser]
}

function Login({ onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()
  async function submit(e) {
    e.preventDefault(); setError('')
    try {
      const result = await api.login(username, password)
      onLogin(result.user); navigate('/')
    } catch (e) { setError(e.message) }
  }
  return <div className="login-page"><div className="login-panel">
    <div className="brand-lockup"><div className="brand-mark">E</div><div><strong>Eaststone</strong><span>CONTROLLED DOCUMENTS & TRAINING</span></div></div>
    <div className="eyebrow">Secure training portal</div><h1>Welcome back</h1><p>Sign in to view controlled procedures and your training position.</p>
    {error && <div className="alert error">{error}</div>}
    <form onSubmit={submit} className="form-stack"><label>Username<input value={username} onChange={e=>setUsername(e.target.value)} required /></label><label>Password<input type="password" value={password} onChange={e=>setPassword(e.target.value)} required /></label><button className="primary">Sign in</button></form>
  </div></div>
}

function Shell({ user, setUser, children }) {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const role = user.role || 'user'
  const can = r => roleRank[role] >= roleRank[r]
  async function logout(){ await api.logout(); setUser(null); navigate('/login') }
  const links = [
    ['/', Gauge, 'Overview', true],
    ['/documents', Files, 'Controlled documents', true],
    ['/team', ClipboardCheck, 'Training matrix', can('manager')],
    ['/people', Users, 'People & roles', can('manager')],
    ['/document-control', FileClock, 'Document control', can('qa')],
    ['/permissions', ShieldCheck, 'Permissions', can('qa')],
    ['/audit', History, 'Audit trail', can('qa')],
    ['/system', Settings, 'System', can('qa')],
  ]
  return <div className="app-shell">
    <header className="topbar"><button className="icon-btn" onClick={()=>setOpen(true)}><Menu /></button><div className="top-brand">EASTSTONE</div><div className="divider"/><div className="subtitle">Controlled Documents & Training</div><div className="user-chip"><strong>{user.name}</strong><span>{role.toUpperCase()}</span></div></header>
    {open && <div className="scrim" onClick={()=>setOpen(false)} />}
    <aside className={`drawer ${open?'open':''}`}>
      <div className="drawer-head"><div className="brand-mark">E</div><div><strong>Eaststone</strong><span>TRAINING MATRIX</span></div><button className="drawer-close" onClick={()=>setOpen(false)}><X/></button></div>
      <p className="drawer-label">WORKSPACE</p><nav>{links.filter(x=>x[3]).map(([to,Icon,label])=><NavLink key={to} to={to} end={to==='/'} onClick={()=>setOpen(false)}><Icon size={22}/><span>{label}</span><b>›</b></NavLink>)}</nav>
      <div className="drawer-user"><div className="avatar">{user.name?.[0]?.toUpperCase()}</div><div><strong>{user.name}</strong><span>{role.toUpperCase()}</span></div><button onClick={logout}><LogOut size={18}/></button></div>
    </aside>
    <main>{children}</main>
  </div>
}

function Donut({ completed, outstanding, overdue, percentage }) {
  const total = completed + outstanding + overdue || 1
  const green = completed / total * 100
  const yellow = outstanding / total * 100
  return <div className="donut-wrap"><div className="donut" style={{'--green':`${green}%`,'--yellow':`${green+yellow}%`}}><div><strong>{percentage}%</strong><span>compliant</span></div></div><div className="legend"><div><i className="green"/>Read & understood <b>{completed}</b></div><div><i className="yellow"/>Outstanding <b>{outstanding}</b></div><div><i className="red"/>Overdue <b>{overdue}</b></div></div></div>
}

function Overview() {
  const [data,setData]=useState(null)
  useEffect(()=>{api.overview().then(setData)},[])
  if(!data) return <Loading/>
  const m=data.metrics
  return <>
    <section className="hero"><div className="eyebrow">Compliance overview</div><h1>Good afternoon, {data.user.name}</h1><p>Your controlled-document and training position at a glance.</p></section>
    <div className="metric-grid">
      <Metric icon={<BookOpenCheck/>} label="Open training" value={m.outstanding} note="Assigned and not completed" tone="green"/>
      <Metric icon={<AlertTriangle/>} label="Overdue" value={m.overdue} note="Requires attention" tone="red"/>
      <Metric icon={<FileClock/>} label="Compliance target" value={`${data.threshold}%`} note="Minimum required" tone="yellow"/>
      <Metric icon={<CheckCircle2/>} label="Completed" value={m.completed} note="Version-specific evidence" tone="blue"/>
    </div>
    <div className="content-grid"><section className="card"><div className="eyebrow">My training position</div><Donut {...m}/></section><section className="card"><div className="eyebrow">Next action</div><h2>{m.percentage < data.threshold ? 'Training requires attention' : 'You are on track'}</h2><p>{m.percentage < data.threshold ? 'Your compliance is below the required threshold. Complete outstanding and overdue procedures.' : 'Continue to review new and revised procedures assigned to you.'}</p><NavLink className="primary button-link" to="/documents">Open controlled documents</NavLink></section></div>
  </>
}

function Metric({icon,label,value,note,tone}){return <div className="metric-card"><div className={`metric-icon ${tone}`}>{icon}</div><div><span>{label}</span><strong>{value}</strong><small>{note}</small></div></div>}

function Documents(){const[q,setQ]=useState('');const[rows,setRows]=useState([]);useEffect(()=>{const t=setTimeout(()=>api.documents(q).then(r=>setRows(r.documents)),180);return()=>clearTimeout(t)},[q]);return <><section className="hero"><div className="eyebrow">Controlled documents</div><h1>Controlled documents</h1><p>Search the current approved procedures available in the system.</p></section><div className="card search-card"><Search/><input placeholder="Find a document by reference or title" value={q} onChange={e=>setQ(e.target.value)}/></div><div className="document-list">{rows.map(d=><NavLink to={`/documents/${d.id}`} key={d.id} className="document-card"><div className="doc-icon"><FileSearch/></div><div><strong>{d.reference}</strong><h3>{d.title}</h3><p>Revision {d.revision || '—'} · {d.category || 'Controlled document'}</p></div><span className={`status ${String(d.status).toLowerCase()}`}>{d.status}</span></NavLink>)}{!rows.length&&<div className="card empty">No documents found.</div>}</div></>}

function DocumentDetail(){const{id}=useParams();const[data,setData]=useState(null);const[error,setError]=useState('');const[form,setForm]=useState({signedName:'',password:''});useEffect(()=>{api.document(id).then(setData)},[id]);if(!data)return <Loading/>;const d=data.document;async function sign(e){e.preventDefault();setError('');try{await api.acknowledge(id,{versionId:d.versionId,...form});setData(await api.document(id));}catch(e){setError(e.message)}}return <><NavLink to="/documents" className="back">← Controlled documents</NavLink><section className="hero"><div className="eyebrow">Current approved procedure</div><h1>{d.reference} — {d.title}</h1><p>Revision {d.revision || '—'} · {d.category || 'Controlled document'}</p></section><div className="card document-open"><div><h2>{d.fileName || 'No active approved file'}</h2><p>Open and read the current approved revision before acknowledging training.</p></div>{d.materialUrl&&<a className="primary button-link" href={d.materialUrl} target="_blank">Open PDF / document</a>}</div>{d.assigned&&d.versionId&&<div className="card"><div className="eyebrow">Read & understood</div><h2>Electronic acknowledgement</h2><p>I confirm that I have read and understood this controlled document.</p>{error&&<div className="alert error">{error}</div>}<form onSubmit={sign} className="form-stack narrow"><label>Electronic signature — type your full name<input value={form.signedName} onChange={e=>setForm({...form,signedName:e.target.value})} required/></label><label>Confirm your password<input type="password" value={form.password} onChange={e=>setForm({...form,password:e.target.value})} required/></label><button className="primary">Read & Understood</button></form></div>}{data.signatures.length>0&&<div className="card"><div className="eyebrow">Evidence history</div><table><thead><tr><th>Date/time</th><th>Revision</th><th>Signature</th><th>Document</th></tr></thead><tbody>{data.signatures.map((s,i)=><tr key={i}><td>{s.signed_at}</td><td>{s.revision}</td><td>{s.signed_name}</td><td>{s.original_name}</td></tr>)}</tbody></table></div>}</>}

function Team(){const[data,setData]=useState([]);useEffect(()=>{api.team().then(r=>setData(r.team))},[]);const avg=useMemo(()=>data.length?Math.round(data.reduce((a,b)=>a+b.percentage,0)/data.length*10)/10:100,[data]);return <><section className="hero"><div className="eyebrow">Training matrix</div><h1>Department training overview</h1><p>Monitor staff compliance and training actions requiring attention.</p></section><div className="metric-grid"><Metric icon={<Gauge/>} label="Overall compliance" value={`${avg}%`} note="Minimum target 80%" tone="green"/><Metric icon={<AlertTriangle/>} label="Below 80%" value={data.filter(x=>x.percentage<80).length} note="Staff requiring attention" tone="red"/><Metric icon={<FileClock/>} label="Outstanding" value={data.reduce((a,b)=>a+b.outstanding,0)} note="Training items to complete" tone="yellow"/><Metric icon={<CheckCircle2/>} label="Completed" value={data.reduce((a,b)=>a+b.trained,0)} note="Current completions" tone="blue"/></div><div className="card table-card"><table><thead><tr><th>Staff member</th><th>Department</th><th>Role</th><th>Compliance</th><th>Read</th><th>Outstanding</th><th>Alert</th></tr></thead><tbody>{data.map(e=><tr key={e.id}><td><strong>{e.name}</strong></td><td>{e.department}</td><td>{e.jobRole||'—'}</td><td><div className="progress"><span style={{width:`${e.percentage}%`}}/></div>{e.percentage}%</td><td>{e.trained}</td><td>{e.outstanding}</td><td>{e.percentage<80?<span className="status overdue">Email alert</span>:<span className="status compliant">Compliant</span>}</td></tr>)}</tbody></table></div></>}

function Audit(){const[events,setEvents]=useState([]);useEffect(()=>{api.audit().then(r=>setEvents(r.events))},[]);return <><section className="hero"><div className="eyebrow">Audit trail</div><h1>System audit trail</h1><p>Review traceable user and system activity.</p></section><div className="card table-card"><table><thead><tr><th>Date/time</th><th>User</th><th>Action</th><th>Entity</th><th>Details</th></tr></thead><tbody>{events.map((e,i)=><tr key={i}><td>{e.created_at}</td><td>{e.username||'System'}</td><td>{e.action}</td><td>{e.entity_type} {e.entity_id||''}</td><td>{e.details}</td></tr>)}</tbody></table></div></>}

function Placeholder({title,eyebrow,children}){return <><section className="hero"><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{children}</p></section><div className="card empty">This administration screen is being moved into the React frontend. The Python backend controls remain available while the migration is completed.</div></>}
function Loading(){return <div className="loading">Loading…</div>}

export default function App(){const[user,setUser]=useAuth();if(user===undefined)return <Loading/>;return <Routes><Route path="/login" element={user?<Navigate to="/"/>:<Login onLogin={setUser}/>}/><Route path="/*" element={user?<Shell user={user} setUser={setUser}><Routes><Route path="/" element={<Overview/>}/><Route path="/documents" element={<Documents/>}/><Route path="/documents/:id" element={<DocumentDetail/>}/><Route path="/team" element={<Team/>}/><Route path="/audit" element={<Audit/>}/><Route path="/people" element={<Placeholder eyebrow="People & roles" title="People & roles">Manage staff, departments, job roles and training assignments.</Placeholder>}/><Route path="/document-control" element={<Placeholder eyebrow="Quality document control" title="Document control">Manage approved procedures, immutable revisions and release status.</Placeholder>}/><Route path="/permissions" element={<Placeholder eyebrow="Access control" title="Permissions">Manage user permission levels and departmental access.</Placeholder>}/><Route path="/system" element={<Placeholder eyebrow="System administration" title="System">Configure approved-folder synchronisation and application settings.</Placeholder>}/></Routes></Shell>:<Navigate to="/login"/>}/></Routes>}
