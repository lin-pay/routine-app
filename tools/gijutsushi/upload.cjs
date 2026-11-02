// 過去問の索引（data/gq_idx）と問題画像（gq/{k}）を本人のアカウント配下に書き込む。既存の文書には触らない
const R='/Users/nagaoka/gcp-migration/rinpe04naga06/private/routine-app';
const {initializeApp,cert}=require(R+'/node_modules/firebase-admin/lib/app');
const {getFirestore}=require(R+'/node_modules/firebase-admin/lib/firestore');
const fs=require('fs'),path=require('path');
const Y=process.argv[2];
const app=initializeApp({credential:cert(JSON.parse(fs.readFileSync(R+'/routine-app-5eff3-firebase-adminsdk-fbsvc-c788b35d58.json','utf8')))});
const db=getFirestore(app);
(async()=>{
  const users=await db.collection('users').listDocuments();
  if(users.length!==1)throw new Error('users: '+users.length);
  const uid=users[0].id;
  const before=await db.collection(`users/${uid}/gq`).listDocuments();
  const idxSnap=await db.doc(`users/${uid}/data/gq_idx`).get();
  console.log('uid',uid,'既存 gq',before.length,'既存 gq_idx',idxSnap.exists);
  const files=fs.readdirSync(path.join(Y,'q')).filter(f=>f.endsWith('.json')).sort();
  let n=0;
  for(let i=0;i<files.length;i+=100){
    const b=db.batch();
    for(const f of files.slice(i,i+100)){b.set(db.doc(`users/${uid}/gq/${f.replace(/\.json$/,'')}`),JSON.parse(fs.readFileSync(path.join(Y,'q',f),'utf8')));n++;}
    await b.commit();
  }
  await db.doc(`users/${uid}/data/gq_idx`).set(JSON.parse(fs.readFileSync(path.join(Y,'idx.json'),'utf8')));
  const after=await db.collection(`users/${uid}/gq`).listDocuments();
  const idx=(await db.doc(`users/${uid}/data/gq_idx`).get()).data();
  const s=(await db.doc(`users/${uid}/gq/R7_shinrin_02`).get()).data();
  console.log('書いた',n,'件 / gq の文書数',after.length,'/ 索引',idx.sets.length,'セット',idx.sets.reduce((a,x)=>a+x.qs.length,0),'問 / サンプル R7_shinrin_02',s.w+'x'+s.h,s.img.slice(0,30),s.t.slice(0,30).replace(/\n/g,' '));
})().catch(e=>{console.error(e);process.exit(1)});
