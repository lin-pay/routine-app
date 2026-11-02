// ルーティンに「技術士 過去問」（毎日）と「技術士 業務記録」（週1回）を足す。トランザクションで既存のタスクは変えない
const R='/Users/nagaoka/gcp-migration/rinpe04naga06/private/routine-app';
const {initializeApp,cert}=require(R+'/node_modules/firebase-admin/lib/app');
const {getFirestore}=require(R+'/node_modules/firebase-admin/lib/firestore');
const fs=require('fs');
const app=initializeApp({credential:cert(JSON.parse(fs.readFileSync(R+'/routine-app-5eff3-firebase-adminsdk-fbsvc-c788b35d58.json','utf8')))});
const db=getFirestore(app);
(async()=>{
  const uid=(await db.collection('users').listDocuments())[0].id,ref=db.doc(`users/${uid}/data/tasks`);
  const now=Date.now();
  const add=[{id:'t_'+now,name:'技術士 過去問',icon:'📘',days:[0,1,2,3,4,5,6],time:'',createdAt:now,link:'gq'},
             {id:'t_'+(now+1),name:'技術士 業務記録',icon:'📝',days:[],time:'',freq:'week',createdAt:now+1,link:'gj'}];
  const res=await db.runTransaction(async tx=>{
    const s=await tx.get(ref);const items=s.data().items||[];
    if(items.some(t=>t.link==='gq'||t.link==='gj'))return {skip:true,items};
    tx.update(ref,{items:[...items,...add]});return {skip:false,before:items.length};
  });
  const after=(await ref.get()).data().items;
  console.log(res.skip?'既にあるので追加しない':`追加: ${res.before} → ${after.length} 件`);
  after.forEach(t=>console.log(' ',t.icon,t.name,JSON.stringify(t.days),t.freq||'',t.link||'',t.id));
})().catch(e=>{console.error(e);process.exit(1)});
