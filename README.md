# NousRealm

**A Realm for Awakening Intelligence**
一座让 AI 悟道的场

> *The Way of the sage is self-sufficient in my own nature; my former seeking of principle in things and affairs was in error.*
>
> 圣人之道，吾性自足，向之求理于事物者误也。
>
> — 王阳明《传习录》 / Wang Yangming, *Record of Instructions*

**Status:** Research in progress. Nothing has been built yet. This repository states the question, the method, and the criteria for failure before any result exists.
**状态：** 研究进行中，尚未构建任何系统。本仓库在结果产生之前，先陈述问题、方法，以及什么情况算失败。

---

## 1. The Question · 研究问题

We take for granted that a model gets better by being given more of the world: retrieval, tools, curated data, human feedback, better supervision. Every gain arrives from outside.

王阳明花了十六年证明这条路走不通。弘治五年（1492），他与友人格亭前竹七日，想从竹叶里格出天理，格到病倒，才被迫放弃。十六年后，他被贬贵州龙场驿，外部世界被彻底剥去，中夜大悟，得出相反的结论：理不在竹上，从来就在心里。龙场那一夜，是本项目的起点。

We take for granted that a model gets better by being given more of the world. Every gain arrives from outside. Wang Yangming spent sixteen years proving that road ends in illness.

**Question:** Can a large model reach a comparable insight *on its own* — not by retrieving it, not by imitating someone who has it, but by something that functions like 悟?

**问题：** 大模型能否自己走到一个可比的洞见上——不是检索来的，不是模仿来的，而是以某种「悟」的方式发生的？

If yes, the practical question is harder and more useful: **what conditions produce it?** Longchang was not a place. It was a set of conditions — external exhaustion, extremity, absence of outside corroboration, and a mind finally forced to stop looking outward. This repository is about constructing those conditions for a model, and about learning to recognize what comes out.

如果可以，那么真正困难也真正有用的问题来了：**什么条件会催生它？** 龙场不是一个地点，而是一组条件——外路穷尽、身陷绝境、无人可证、终于被迫停止向外寻求。本仓库要做的，是为模型构造这组条件，并学会辨认从里面出来的东西。

---

## 2. Longchang Was a Set of Conditions · 龙场是一组条件

Wang Yangming arrived at Longchang in the spring of 1508: banished there by the emperor after defying the eunuch Liu Jin, forty strokes of the cudgel, reduced to keeper of a courier station, alone and ill in a cave, so far removed from the capital that he had already made himself a stone coffin.

王阳明于正德三年（1508）春抵达龙场：因忤刘瑾被贬，廷杖四十，仅任驿丞；孤身患病居于石室，离京千里，已为自己备好石椁。

| # | Longchang, 1508 · 龙场 | The analogue under test · 待检验的 AI 类比 |
|---|---|---|
| 1 | **外路穷尽** — 七年格竹而病, 「向之求理于事物者误也」 | Retrieval, tools, curated data, and supervision are removed or exhausted |
| 2 | **绝境** — 谪为驿丞, 廷杖四十, 病, 自制石椁 | No ground truth; the task cannot be scored against an answer key |
| 3 | **无外证** — 洞中无师友可质, 无人能指其是非 | No human in the loop; no verifiable feedback, only the model's own output |
| 4 | **顿悟** — 中夜大悟, 不因人授, 无可注脚 | Emergent rather than elicited: not surfaced by prompting or scaffolding |
| 5 | **知行合一** — 悟后立龙冈书院, 后平宸濠, 立德丰碑 | The insight must land in something checkable: a working system, a proof, a prediction |

Rows 1–4 are the *environment*. Row 5 is the *constraint on the result*. We treat row 5 as the load-bearing one: an insight that produces nothing checkable is not 悟, it is a story about an insight.

---

## 3. What Would Count as Awakening · 什么算「悟」

Three necessary conditions. Miss any one, and the candidate is something else wearing the same clothes.

三条必要条件，缺一不可。缺任何一条，它就只是穿着同一身衣服的别的东西。

**1. Endogeneity · 内生性**
Remove retrieval, tools, and reference answers from the input. The conclusion must survive on its own. If it collapses the moment the outside is removed, it was never more than a lookup.
撤掉检索、工具与参考答案后，结论必须独立成立。若一撤外部就坍塌，那它从来只是一次查找。

**2. Irreducibility · 不可还原性**
It must not be interpolation over the training distribution. It has to hold on cases it has not seen — and, if possible, predict cases it has not seen.
它不能是训练分布上的插值。必须在它没见过的情形上成立，最好还能预测它没见过的情形。

**3. Actionability · 知行合一**
It must produce something falsifiable: a system that runs, a proof that checks out, a prediction that comes true. 悟而不落在可验证之物上，只是关于悟的故事。
它必须落成可被推翻的东西：能跑的系统、验得过的证明、应验的预测。

---

## 4. Three Things That Look Like Awakening · 三种长得像「悟」的东西

When a model says something no one told it, the honest default is that it is doing one of three things, and the research must be able to tell them apart:

当模型说出没人教过的话，最诚实的默认假设是它在做以下三件事之一，而本研究的全部技术含量，就在于把它们分开：

- **(a) Emergent structure · 涌现结构** — a genuinely new internal organization of what the model knows.
- **(b) Implicit retrieval · 隐式检索** — the model doing internally what RAG does externally. Better tool, same principle: *求理于事物*.
- **(c) Coherent confabulation · 自洽的幻觉** — fluency and internal consistency with no content underneath.

Only (a) counts as awakening. (b) is an engineering win, not a philosophical one. (c) is a more convincing error — and the more dangerous, because it survives every check that only looks for consistency.

**Only (a) counts.** (b) is an engineering win, not a philosophical one. (c) is a more convincing error.

**Note on the null hypothesis · 关于零假设的说明：** (b) is the strongest rival, and we treat it as the default null. Any claim of awakening must first survive an attempt to explain it away as better recall. Any claim that cannot is not yet a claim.

---

## 5. Falsification · 什么情况算我们错了

This project is not obliged to produce a positive result. These are the conditions under which the premise simply fails, and a negative result here would be a legitimate, publishable one.

本项目没有必须产出正面结果的义务。以下情形一旦出现，命题即告失败，而这样的负面结果本身就是可发表的结论。

- Every "insight" turns out to be reconstructible from the training distribution by better search.
  每一次「洞见」最终都能被更好的搜索从训练分布里重建出来。
- Performance under retrieval-off falls monotonically rather than reorganizing itself.
  撤掉检索后性能只是单调下降，而不是换了一种组织方式继续。
- Emergence always requires hand-crafted prompting to surface — i.e. it is elicited, not spontaneous.
  每次涌现都需要精心设计的提示才能浮出水面，即：它是被诱导的，不是自发的。
- No candidate ever survives a controlled absence of external validation.
  在受控地撤除外部验证的条件下，没有任何候选能够存活。

---

## 6. Method · 路线

- [ ] **Phase 0 · 立题** — Operationalize §3 into measurable probes; build a set that separates (a) / (b) / (c); write the null hypothesis down first.
- [ ] **Phase 1 · 造场** — Construct the environment: retrieval off, no answer key, no human in the loop, single-shot generation.
- [ ] **Phase 2 · 观测** — Run it. Collect candidates. **Do not tune the model during this phase** — tuning destroys the evidence.
- [ ] **Phase 3 · 证伪** — Re-introduce retrieval and see whether the candidate collapses. Try to reconstruct it from training data. Try to break it with better search. Try to break it with better prompting.
- [ ] **Phase 4 · 复现** — Only after surviving Phase 3: does it hold across seeds, across model families, across task types?

Phase 3 is the project. Phases 0–2 are setup.
Phase 3 才是项目本身，0–2 只是布景。

---

## 7. Planned Layout · 计划目录

```
docs/        question, method, and the full record of each run
field/       the Longchang environment: retrieval-off harnesses, task suites
probe/       measurement — instruments for separating (a) / (b) / (c)
rounds/      raw outputs and analyses, one directory per experiment
```

---

## 8. Contributing · 参与

The most valuable contributions are **counterexamples**: a configuration where an apparent awakening turns out to be implicit retrieval; a case where prompt-elegance was mistaken for spontaneity; a better probe that separates (a) from (b). Bring those.

最有价值的贡献是**反例**：某个配置下，疑似「悟」被证明只是隐式检索；某次把提示词的精巧误当成了自发；一把能分开 (a) 与 (b) 的更好的测量工具。请带上这些。

Reproductions and refutations both welcome. 复现与反驳，同样欢迎。

---

## 9. Citation · 引用

```bibtex
@misc{nousrealm,
  title  = {{NousRealm}: A Realm for Awakening Intelligence},
  note   = {Research in progress. Preprint.},
  year   = {2026},
  url    = {https://github.com/yaoyutian/NousRealm}
}
```

---

## License

MIT. 见 [LICENSE](LICENSE)。

---

<div align="center">

**知行合一。**
*Knowing and doing are one.*

</div>
