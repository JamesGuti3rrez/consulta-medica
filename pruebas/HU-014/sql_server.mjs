// Adaptador HTTP de pruebas para la migración real de PostgreSQL. Solo escucha en loopback.
import http from 'node:http';
import { createDatabase,rpc,IDS } from './sql_fixture.mjs';
let db=await createDatabase();
const server=http.createServer(async(req,res)=>{
  const reply=(status,data)=>{res.writeHead(status,{'Content-Type':'application/json'});res.end(JSON.stringify(data));};
  try {
    const url=new URL(req.url,'http://127.0.0.1:3039');let raw='';for await(const chunk of req){raw+=chunk;if(raw.length>5000000)throw Error('Petición demasiado grande');}const body=raw?JSON.parse(raw):{};
    if(url.pathname==='/__health')return reply(200,{ok:true,motor:'PostgreSQL PGlite',fixture:true});
    if(url.pathname==='/__reset'&&req.method==='POST'){await db.close();db=await createDatabase();return reply(200,{ok:true});}
    if(url.pathname==='/__clear_groups'&&req.method==='POST'){
      await db.exec('truncate public.diagnosticos_finales,public.doctor_participaciones,public.doctor_asignaciones,public.doctor_grupo_miembros,public.doctor_grupos,public.sma_eventos,public.sma_sesiones restart identity cascade');
      return reply(200,{ok:true});
    }
    if(url.pathname==='/auth/v1/user'){
      const token=(req.headers.authorization||'').replace(/^Bearer /,'');const id=IDS[token];if(!id)return reply(401,{error:'Credencial de fixture no válida'});
      const user=(await db.query('select * from auth.users where id=$1',[id])).rows[0];return reply(200,{id:user.id,email:user.email,app_metadata:user.raw_app_meta_data,user_metadata:user.raw_user_meta_data});
    }
    const path=url.pathname.replace('/rest/v1/','');
    if(path.startsWith('rpc/')&&req.method==='POST')return reply(200,await rpc(db,path.slice(4),body));
    const sid=(url.searchParams.get('session_id')||'').replace(/^eq\./,'');
    if(path==='sma_sesiones'){
      if(req.method==='POST'){await db.query('insert into public.sma_sesiones(session_id,case_id,phase,state) values($1,$2,$3,$4)',[body.session_id,body.case_id,body.phase,JSON.stringify(body.state)]);return reply(201,{});}
      if(req.method==='PATCH'){const excluded=(url.searchParams.get('phase')||'').replace(/^neq\./,'')||null;const r=await db.query('update public.sma_sesiones set phase=$1,state=$2,updated_at=now() where session_id=$3 and ($4::text is null or phase<>$4) returning session_id',[body.phase,JSON.stringify(body.state),sid,excluded]);return reply(200,r.rows);}
      return reply(200,(await db.query('select * from public.sma_sesiones where session_id=$1',[sid])).rows);
    }
    if(path==='sma_eventos'){
      if(req.method==='POST'){await db.query('insert into public.sma_eventos(session_id,payload) values($1,$2)',[body.session_id,JSON.stringify(body.payload)]);return reply(201,{});}
      return reply(200,(await db.query('select payload from public.sma_eventos where session_id=$1 order by id',[sid])).rows);
    }
    if(path==='diagnosticos_finales'){
      // HU-006: lo mismo que pide SupabaseDiagnoses a PostgREST (por sesión, último intento del alumno en el caso, alta).
      if(req.method==='POST'){
        try{const r=await db.query('insert into public.diagnosticos_finales(session_id,usuario_id,case_id,numero_intento,diagnostico,hipotesis) values($1,$2,$3,$4,$5,$6) returning *',[body.session_id,body.usuario_id,body.case_id,body.numero_intento,body.diagnostico,JSON.stringify(body.hipotesis||[])]);return reply(201,r.rows);}
        catch(e){if(e.code==='23505')return reply(409,{code:'23505',message:e.message});throw e;}
      }
      const by=key=>(url.searchParams.get(key)||'').replace(/^eq\./,'');
      if(by('session_id'))return reply(200,(await db.query('select * from public.diagnosticos_finales where session_id=$1',[by('session_id')])).rows);
      return reply(200,(await db.query('select numero_intento from public.diagnosticos_finales where usuario_id=$1 and case_id=$2 order by numero_intento desc limit 1',[by('usuario_id'),by('case_id')])).rows);
    }
    if(path==='casos_curados'){
      const cid=(url.searchParams.get('case_id')||'').replace(/^eq\./,'');
      const limit=Number(url.searchParams.get('limit')??100),offset=Number(url.searchParams.get('offset')??0);
      return reply(200,(await db.query('select * from public.casos_curados where ($1::text=\'\' or case_id=$1) order by case_id limit $2 offset $3',[cid,limit,offset])).rows);
    }
    if(['rag_evidencias','caso_datos_adicionales'].includes(path))return reply(200,[]);
    reply(404,{code:'PGRST202',message:'Ruta no incluida en el fixture'});
  }catch(e){reply(e.code==='P0002'?404:e.code==='42501'?403:400,{code:e.code||'FIXTURE_ERROR',message:e.message});}
});
const port=Number(process.env.HU014_SQL_PORT||3039);
server.listen(port,'127.0.0.1',()=>console.log('HU-014 PostgreSQL de pruebas en 127.0.0.1:'+port+'. Datos sintéticos; no es Supabase productivo.'));
