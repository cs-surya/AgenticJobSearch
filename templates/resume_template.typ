#let d = json(sys.inputs.data_path)

#set page(
  paper: "a4",
  margin: (x: 1.25cm, top: 1.1cm, bottom: 1.1cm)
)
#set text(
  font: ("Liberation Sans", "Helvetica", "Arial"),
  size: 9.2pt,
  fill: rgb("#000000")
)
#set par(justify: false, leading: 0.45em)

// ---------------- HEADER ----------------
#align(center)[
  #text(size: 16pt, weight: "bold")[#d.name] \
  #v(0.2em)
  #text(size: 9pt)[
    #if d.phone != "" [#d.phone | ]
    #if d.email != "" [#d.email]
  ] \
  #v(0.1em)
  #text(size: 9pt)[
    #if d.website != "" [#d.website | ]
    #if d.github != "" [#d.github | ]
    #if d.linkedin != "" [#d.linkedin]
  ]
]

#v(0.4em)

// ---------------- EDUCATION ----------------
#if d.education.len() > 0 [
  #text(size: 10.5pt, weight: "bold")[EDUCATION]
  #v(-0.55em)
  #line(length: 100%, stroke: 0.75pt + rgb("#000000"))
  #v(0.15em)
  #for edu in d.education [
    #grid(
      columns: (1fr, auto),
      [ *#edu.degree* ],
      [ *#edu.dates* ]
    )
    #v(-0.35em)
    #text(fill: rgb("#222222"))[#edu.institution]
    #v(0.35em)
  ]
  #v(0.2em)
]

// ---------------- WORK EXPERIENCE ----------------
#if d.experiences.len() > 0 [
  #text(size: 10.5pt, weight: "bold")[WORK EXPERIENCE]
  #v(-0.55em)
  #line(length: 100%, stroke: 0.75pt + rgb("#000000"))
  #v(0.15em)
  #for exp in d.experiences [
    #grid(
      columns: (1fr, auto),
      [ *#exp.role* -- *#exp.company* ],
      [ *#exp.dates* ]
    )
    #v(-0.35em)
    #text(fill: rgb("#333333"))[_#exp.location_]
    #v(0.2em)
    #for hl in exp.highlights [
      #grid(
        columns: (1.2em, 1fr),
        [●],
        [#hl]
      )
      #v(0.15em)
    ]
    #v(0.35em)
  ]
  #v(0.2em)
]

// ---------------- PROJECTS ----------------
#if d.projects.len() > 0 [
  #text(size: 10.5pt, weight: "bold")[PROJECTS]
  #v(-0.55em)
  #line(length: 100%, stroke: 0.75pt + rgb("#000000"))
  #v(0.15em)
  #for proj in d.projects [
    *#proj.title* \
    #v(-0.35em)
    #for hl in proj.highlights [
      #grid(
        columns: (1.2em, 1fr),
        [●],
        [#hl]
      )
      #v(0.15em)
    ]
    #v(0.35em)
  ]
]