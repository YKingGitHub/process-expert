/* Minimal local WebGL CAD comparison. Both panes use the same union bounds.
 * Preview tessellation only; authoritative geometry metrics use OpenCascade BREP.
 */
window.CadPair = class {
  constructor(left, right, reference, rebuilt, referenceBounds, rebuiltBounds) {
    this.yaw = -.65; this.pitch = -.5; this.zoom = 1; this.disposed = false;
    // One common display frame, not per-model centering/alignment. This keeps
    // displaced candidates visible without hiding their coordinate mismatch.
    const bounds = referenceBounds.map((v,i)=>i<3?Math.min(v,rebuiltBounds[i]):Math.max(v,rebuiltBounds[i]));
    this.center = bounds.slice(0,3).map((v,i)=>(v+bounds[i+3])/2);
    this.span = Math.max(...bounds.slice(0,3).map((v,i)=>bounds[i+3]-v));
    this.panes = [[left, reference, [.14,.47,.68]], [right, rebuilt, [.77,.44,.19]]].map(([c,m,color])=>this.setup(c,m,color));
    for (const pane of this.panes) {
      let last = null; const c=pane.canvas;
      c.addEventListener('pointerdown',e=>{last=[e.clientX,e.clientY];c.setPointerCapture(e.pointerId);});
      c.addEventListener('pointermove',e=>{if(!last)return;this.yaw+=(e.clientX-last[0])*.009;this.pitch+=(e.clientY-last[1])*.009;last=[e.clientX,e.clientY];this.draw();});
      c.addEventListener('pointerup',()=>{last=null;});c.addEventListener('pointercancel',()=>{last=null;});
      c.addEventListener('wheel',e=>{e.preventDefault();this.zoom=Math.max(.15,Math.min(8,this.zoom*Math.exp(-e.deltaY*.001)));this.draw();},{passive:false});
    }
    this.observer=new ResizeObserver(()=>this.draw());this.panes.forEach(p=>this.observer.observe(p.canvas));this.draw();
  }
  setup(canvas, mesh, color) {
    const gl=canvas.getContext('webgl',{antialias:true});if(!gl)throw new Error('浏览器不支持 WebGL');
    const vertex=`attribute vec3 pos;attribute vec3 normal;uniform mat3 rotation;uniform vec2 aspect;uniform float zoom;varying float light;void main(){vec3 p=rotation*pos;vec3 n=normalize(rotation*normal);light=.38+.62*abs(dot(n,normalize(vec3(-.4,.7,1.))));gl_Position=vec4(p.x*aspect.x*zoom,p.y*aspect.y*zoom,-p.z*.09,1.);}`;
    const frag=`precision mediump float;varying float light;uniform vec3 color;void main(){gl_FragColor=vec4(color*light,1.);}`;
    function shader(type,src){const s=gl.createShader(type);gl.shaderSource(s,src);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw new Error(gl.getShaderInfoLog(s));return s;}
    const program=gl.createProgram();gl.attachShader(program,shader(gl.VERTEX_SHADER,vertex));gl.attachShader(program,shader(gl.FRAGMENT_SHADER,frag));gl.linkProgram(program);gl.useProgram(program);
    const data=[];
    for(const t of mesh.triangles){const a=mesh.vertices[t[0]],b=mesh.vertices[t[1]],c=mesh.vertices[t[2]];const u=b.map((v,i)=>v-a[i]),v=c.map((x,i)=>x-a[i]);let n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]];const l=Math.hypot(...n)||1;n=n.map(x=>x/l);for(const p of [a,b,c])data.push(...p.map((x,i)=>(x-this.center[i])*1.55/this.span),...n);}
    const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(data),gl.STATIC_DRAW);
    for(const [name,offset] of [['pos',0],['normal',12]]){const a=gl.getAttribLocation(program,name);gl.enableVertexAttribArray(a);gl.vertexAttribPointer(a,3,gl.FLOAT,false,24,offset);}
    gl.enable(gl.DEPTH_TEST);gl.clearColor(.965,.976,.98,1);gl.uniform3fv(gl.getUniformLocation(program,'color'),color);
    return {gl,canvas,program,count:data.length/6};
  }
  preset(name){if(name==='iso'){this.yaw=-.65;this.pitch=-.5;}if(name==='xy'){this.yaw=0;this.pitch=0;}if(name==='xz'){this.yaw=0;this.pitch=Math.PI/2;}if(name==='yz'){this.yaw=Math.PI/2;this.pitch=0;}this.zoom=1;this.draw();}
  draw(){if(this.disposed)return;const cy=Math.cos(this.yaw),sy=Math.sin(this.yaw),cx=Math.cos(this.pitch),sx=Math.sin(this.pitch);const r=[cy,sx*sy,-cx*sy,0,cx,sx,sy,-sx*cy,cx*cy];for(const p of this.panes){const {gl,canvas,program}=p;const w=Math.max(1,Math.round(canvas.clientWidth*devicePixelRatio)),h=Math.max(1,Math.round(canvas.clientHeight*devicePixelRatio));if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}gl.viewport(0,0,w,h);gl.useProgram(program);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.uniformMatrix3fv(gl.getUniformLocation(program,'rotation'),false,r);gl.uniform2fv(gl.getUniformLocation(program,'aspect'),w>h?[h/w,1]:[1,w/h]);gl.uniform1f(gl.getUniformLocation(program,'zoom'),this.zoom);gl.drawArrays(gl.TRIANGLES,0,p.count);}}
  dispose(){this.disposed=true;this.observer.disconnect();this.panes.forEach(p=>p.gl.getExtension('WEBGL_lose_context')?.loseContext());}
};
