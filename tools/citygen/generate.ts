// Headless, seeded run of the City Map Generator pipeline (same steps as ui/main_gui.ts):
// coast + river -> main -> major -> minor roads -> parks -> building lots. Writes JSON (map units).
//   node out/headless/generate.js <seed> <out.json> [layout.json]
import fs = require('fs');
import Vector from '../src/ts/vector';
import TensorField from '../src/ts/impl/tensor_field';
import {RK4Integrator} from '../src/ts/impl/integrator';
import StreamlineGenerator from '../src/ts/impl/streamlines';
import WaterGenerator from '../src/ts/impl/water_generator';
import Graph from '../src/ts/impl/graph';
import PolygonFinder from '../src/ts/impl/polygon_finder';

const seed = parseInt(process.argv[2] || '1', 10);
const outPath = process.argv[3] || 'map.json';
const layoutPath = process.argv[4];
// Seeded Math.random (mulberry32): the same seed gives the same city.
let s = seed >>> 0;
Math.random = () => { s = (s + 0x6D2B79F5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };

// Layout: basis fields (grids with their own angle = districts, radials = plazas / old towns).
const layout = layoutPath ? JSON.parse(fs.readFileSync(layoutPath, 'utf8')) : {
    size: [1600, 1100],
    grids: [[400, 300, 600, 30, 0.2], [1200, 350, 500, 30, 0.75], [450, 850, 500, 25, 0.05], [1150, 850, 500, 25, 0.5]],
    radials: [[820, 560, 220, 30]],
    water: true,
};
const origin = new Vector(0, 0);
const dims = new Vector(layout.size[0], layout.size[1]);
const field = new TensorField({globalNoise: false, noiseSizePark: 20, noiseAnglePark: 90, noiseSizeGlobal: 30, noiseAngleGlobal: 20});
for (const g of layout.grids) field.addGrid(new Vector(g[0], g[1]), g[2], g[3], g[4]);
for (const r of layout.radials) field.addRadial(new Vector(r[0], r[1]), r[2], r[3]);

const minor = {dsep: 20, dtest: 15, dstep: 1, dlookahead: 40, dcirclejoin: 5, joinangle: 0.1, pathIterations: 1000, seedTries: 300, simplifyTolerance: 0.5, collideEarly: 0};
const major = Object.assign({}, minor, {dsep: 100, dtest: 30, dlookahead: 200});
const main = Object.assign({}, minor, {dsep: 400, dtest: 200, dlookahead: 500});
const waterParams: any = Object.assign({coastNoise: {noiseEnabled: true, noiseSize: 30, noiseAngle: 20}, riverNoise: {noiseEnabled: true, noiseSize: 30, noiseAngle: 20}, riverBankSize: 10, riverSize: 30}, minor, {pathIterations: 10000, simplifyTolerance: 10});
const integrator = new RK4Integrator(field, minor);
const iters = Math.ceil(Math.max(dims.x, dims.y) * 2.5);
for (const p of [minor, major, main] as any[]) p.pathIterations = iters;

// The UI resolves each step from its frame loop (update()); drive that loop here.
async function drive(p: Promise<void>, gen: {update(): boolean}): Promise<void> {
    let done = false;
    p.then(() => { done = true; });
    while (!done) {
        gen.update();
        await new Promise(r => setImmediate(r));
    }
}

async function run(): Promise<void> {
    const t0 = Date.now();
    const water = new WaterGenerator(integrator, origin, dims, Object.assign({}, waterParams), field);
    if (layout.water) { water.createCoast(); water.createRiver(); }
    const mainGen = new StreamlineGenerator(integrator, origin, dims, main);
    mainGen.addExistingStreamlines(water);
    await drive(mainGen.createAllStreamlines(false), mainGen);
    const majorGen = new StreamlineGenerator(integrator, origin, dims, major);
    majorGen.addExistingStreamlines(water); majorGen.addExistingStreamlines(mainGen);
    await drive(majorGen.createAllStreamlines(false), majorGen);
    const minorGen = new StreamlineGenerator(integrator, origin, dims, minor);
    for (const g of [water, mainGen, majorGen]) minorGen.addExistingStreamlines(g);
    await drive(minorGen.createAllStreamlines(false), minorGen);
    const roads = mainGen.allStreamlinesSimple.concat(majorGen.allStreamlinesSimple, minorGen.allStreamlinesSimple);
    // parks: a couple of blocks of the main + major network
    const big = new PolygonFinder(new Graph(majorGen.allStreamlinesSimple.concat(mainGen.allStreamlinesSimple), minor.dstep).nodes, {maxLength: 20, minArea: 80, shrinkSpacing: 4, chanceNoDivide: 1}, field);
    big.findPolygons();
    const parks = big.polygons.length > 2 ? [big.polygons[Math.floor(Math.random() * big.polygons.length)]] : [];
    field.parks = parks;
    // building lots
    const g = new Graph(mainGen.allStreamlinesSimple.concat(majorGen.allStreamlinesSimple, minorGen.allStreamlinesSimple, (water as any).streamlinesWithSecondaryRoad || []), minor.dstep, true);
    const lots = new PolygonFinder(g.nodes, {maxLength: 20, minArea: 50, shrinkSpacing: 4, chanceNoDivide: 0.05}, field);
    lots.findPolygons();
    await drive(lots.shrink(false), lots);
    await drive(lots.divide(false), lots);
    const r = (vs: Vector[]): number[][] => vs.map(v => [Math.round(v.x * 10) / 10, Math.round(v.y * 10) / 10]);
    const out = {seed, size: layout.size, layout,
        main: mainGen.allStreamlinesSimple.map(r), major: majorGen.allStreamlinesSimple.map(r), minor: minorGen.allStreamlinesSimple.map(r),
        coast: r(water.coastline || []), sea: r(water.seaPolygon || []), river: r(water.riverPolygon || []),
        parks: parks.map(r), lots: lots.polygons.map(r), intersections: g.intersections.map(v => [Math.round(v.x), Math.round(v.y)])};
    fs.writeFileSync(outPath, JSON.stringify(out));
    console.log(`MAPGEN seed ${seed}: ${out.main.length} main, ${out.major.length} major, ${out.minor.length} minor roads, ${out.lots.length} lots, ${out.parks.length} parks in ${((Date.now() - t0) / 1000).toFixed(1)} s -> ${outPath}`);
}
run().catch(e => { console.error(e); process.exit(1); });
