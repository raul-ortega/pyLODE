from typing import Union
from pylode import __version__
from pylode.common import TEMPLATES_DIR, STYLE_DIR
import collections
from os import path
from itertools import chain
import markdown
from jinja2 import Environment, FileSystemLoader
from os.path import join
from rdflib import URIRef, BNode, Literal
from rdflib.namespace import DC, DCTERMS, DOAP, OWL, PROF, PROV, RDF, RDFS, SDO, SKOS
from pylode.profiles.base import BaseProfile
from natsort import natsorted

import re


class OntDoc(BaseProfile):
    def __init__(
            self,
            g,
            source_info,
            outputformat="html",
            include_css=False,
            default_language="en",
            use_curies_stored=True,
            get_curies_online=False
    ):
        super().__init__(
            g,
            source_info,
            outputformat=outputformat,
            include_css=include_css,
            use_curies_stored=use_curies_stored,
            get_curies_online=get_curies_online,
            default_language=default_language)
        self.G.bind("prov", PROV)
        self.CLASSES = collections.OrderedDict()
        self.PROPERTIES = collections.OrderedDict()
        self.NAMED_INDIVIDUALS = collections.OrderedDict()

    def _make_collection_class_html(self, col_type, col_members):
        if col_type == "owl:unionOf":
            j = " or "
        elif col_type == "owl:intersectionOf":
            j = " and "
        else:
            j = " ? "
        # others...
        return "({})".format(
            j.join([self._make_formatted_uri(x, type="c") for x in col_members])
        )

    def _make_restriction_html(self, subject, restriction_bn):
        prop = None
        card = None
        cls = None

        for p2, o2 in self.G.predicate_objects(subject=restriction_bn):
            if p2 != RDF.type:
                if p2 == OWL.onProperty:
                    # TODO: add the property type for HTML
                    t = None
                    if str(o2) in self.PROPERTIES.keys():
                        t = self.PROPERTIES[str(o2)]["prop_type"]
                    #prop = self._make_formatted_uri(str(o2), t)
                    prop = self._build_link(uri=str(o2), source="_make_restrictions_html")
                elif p2 == OWL.onClass:
                    """
                    domains = []
                    for o in self.G.objects(subject=s, predicate=RDFS.domain):
                        if type(o) != BNode:
                            domains.append(str(o))  # domains that are just classes
                        else:
                            # domain collections (unionOf | intersectionOf
                            q = '''
                                PREFIX owl:  <http://www.w3.org/2002/07/owl#>
                                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

                                SELECT ?col_type ?col_member
                                WHERE {{
                                    <{}> rdfs:domain ?domain .
                                    ?domain owl:unionOf|owl:intersectionOf ?collection .
                                    ?domain ?col_type ?collection .
                                    ?collection rdf:rest*/rdf:first ?col_member .
                                }}
                            '''.format(s)
                            collection_type = None
                            collection_members = []
                            for r in self.G.query(q):
                                collection_type = self._get_curie(str(r.col_type))
                                collection_members.append(str(r.col_member))
                            domains.append((collection_type, collection_members))
                    self.PROPERTIES[prop]['domains'] = domains

                    """
                    if type(o2) == BNode:
                        # onClass collections (unionOf | intersectionOf
                        q = """
                            PREFIX owl:  <http://www.w3.org/2002/07/owl#>
                            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

                            SELECT ?col_type ?col_member
                            WHERE {{
                                <{}> owl:onClass ?onClass .
                                ?onClass owl:unionOf|owl:intersectionOf ?collection .
                                ?onClass ?col_type ?collection .
                                ?collection rdf:rest*/rdf:first ?col_member .
                            }}
                        """.format(
                            str(subject)
                        )
                        collection_type = None
                        collection_members = []
                        for r in self.G.query(q):
                            collection_type = self._get_curie(str(r.col_type))
                            collection_members.append(str(r.col_member))

                        cls = self._make_collection_class_html(
                            collection_type, collection_members
                        )
                    else:
                        #cls = self._make_formatted_uri(str(o2), type="c")
                        cls = self._build_link(uri=str(o2), type="c", source="_make_restrictions_html")
                elif p2 in [
                    OWL.cardinality,
                    OWL.qualifiedCardinality,
                    OWL.minCardinality,
                    OWL.minQualifiedCardinality,
                    OWL.maxCardinality,
                    OWL.maxQualifiedCardinality,
                ]:
                    if p2 in [OWL.minCardinality, OWL.minQualifiedCardinality]:
                        card = "min"
                    elif p2 in [OWL.maxCardinality, OWL.maxQualifiedCardinality]:
                        card = "max"
                    elif p2 in [OWL.cardinality, OWL.qualifiedCardinality]:
                        card = "exactly"

                    if self.outputformat in ["md", "adoc"]:
                        card = '**{}** {}'.format(
                            card, str(o2)
                        )
                    else:
                        card = '<span class="cardinality">{}</span> {}'.format(
                            card, str(o2)
                        )
                elif p2 in [OWL.allValuesFrom, OWL.someValuesFrom]:
                    if p2 == OWL.allValuesFrom:
                        card = "only"
                    else:  # p2 == OWL.someValuesFrom
                        card = "some"

                    if type(o2) == BNode:
                        # someValuesFrom collections (unionOf | intersectionOf
                        q = """
                            PREFIX owl:  <http://www.w3.org/2002/07/owl#>
                            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

                            SELECT ?col_type ?col_member
                            WHERE {{
                                <{0}> ?x _:{1} .
                                _:{1} owl:someValuesFrom|owl:allValuesFrom ?bn2 .
                                ?bn2 owl:unionOf|owl:intersectionOf ?collection .
                                ?s ?col_type ?collection .
                                ?collection rdf:rest*/rdf:first ?col_member .
                            }}
                        """.format(
                            str(subject), str(o2)
                        )
                        collection_type = None
                        collection_members = []
                        for r in self.G.query(q):
                            collection_type = self._get_curie(str(r.col_type))
                            collection_members.append(str(r.col_member))

                        c = self._make_collection_class_html(
                            collection_type, collection_members
                        )
                    else:
                        c = self._make_formatted_uri(str(o2), type="c")

                    if self.outputformat in ["md", "adoc"]:
                        card = '**{}** {}'.format(card, c)
                    else:
                        card = '<span class="cardinality">{}</span> {}'.format(card, c)
                elif p2 == OWL.hasValue:
                    if self.outputformat in ["md", "adoc"]:
                        card = '**value** {}'.format(
                            self._make_formatted_uri(str(o2), type="c")
                        )
                    else:
                        card = '<span class="cardinality">value</span> {}'.format(
                            self._make_formatted_uri(str(o2), type="c")
                        )

        restriction = prop + " " + card if card is not None else prop
        restriction = restriction + " " + cls if cls is not None else restriction

        return restriction

    def _load_template(self, template_file):
        return Environment(loader=FileSystemLoader(join(TEMPLATES_DIR, "ontdoc"))).get_template(template_file)

    def _make_fragment_uri(self, uri):
        """OntDoc Profile allows fragment URIs for Classes & Properties"""
        if self.PROPERTIES.get(uri) or self.CLASSES.get(uri):
            if self.PROPERTIES.get(uri):
                title = self.PROPERTIES[uri]["title"] \
                    if self.PROPERTIES[uri].get("title") is not None else self.PROPERTIES[uri]["fid"]
                uri = self.PROPERTIES[uri]["fid"]
            elif self.CLASSES.get(uri):
                title = self.CLASSES[uri]["title"] \
                    if self.CLASSES[uri].get("title") is not None else self.CLASSES[uri]["fid"]
                uri = self.CLASSES[uri]["fid"]

            links = {
                "md": f"[{title}](#{uri})",
                "adoc": f"link:#{uri}[{title}]",
                "html": f'<a href="#{uri}">{title}</a>'
            }

            return links[self.outputformat]
        else:
            return self._make_formatted_uri_basic(uri)

    def _make_formatted_uri(self, uri, type=None):
        link = super()._make_formatted_uri(uri)

        types = {
            "c": "class",
            "op": "object property",
            "fp": "functional property",
            "dp": "datatype property",
            "ap": "annotation property",
            "ni": "named individual"
        }

        if type not in types.keys():
            return link

        suffixes = {
            "md": f' ({type})',
            "adoc": f' ^{type}^',
            "html": f'<sup class="sup-{type}" title="{types[type]}">{type}</sup>'  # {}
        }

        return link + suffixes[self.outputformat]

    def _expand_graph(self):
        # name
        for s, o in chain(
                self.G.subject_objects(DC.title),
                self.G.subject_objects(RDFS.label),
                self.G.subject_objects(SKOS.prefLabel),
                self.G.subject_objects(SDO.name)
        ):
            self.G.add((s, DCTERMS.title, o))

        # description
        for s, o in chain(
                self.G.subject_objects(DC.description),
                self.G.subject_objects(RDFS.comment),
                self.G.subject_objects(SKOS.definition),
                self.G.subject_objects(SDO.description)
        ):
            self.G.add((s, DCTERMS.description, o))

        # property types
        for s in chain(
                self.G.subjects(RDF.type, OWL.ObjectProperty),
                self.G.subjects(RDF.type, OWL.FunctionalProperty),
                self.G.subjects(RDF.type, OWL.DatatypeProperty),
                self.G.subjects(RDF.type, OWL.AnnotationProperty)
        ):
            self.G.add((s, RDF.type, RDF.Property))

        # class types
        for s in self.G.subjects(RDF.type, OWL.Class):
            self.G.add((s, RDF.type, RDFS.Class))

        # owl:Restrictions from Blank Nodes
        for s in self.G.subjects(OWL.onProperty):
            self.G.add((s, RDF.type, OWL.Restriction))

        # Agents
        # creator
        for s, o in chain(
                self.G.subject_objects(DC.creator),
                self.G.subject_objects(SDO.creator),
                self.G.subject_objects(SDO.author)  # conflate SDO.author with DCTERMS.creator
        ):
            self.G.remove((s, DC.creator, o))
            self.G.remove((s, SDO.creator, o))
            self.G.remove((s, SDO.author, o))
            self.G.add((s, DCTERMS.creator, o))

        # contributor
        for s, o in chain(
                self.G.subject_objects(DC.contributor),
                self.G.subject_objects(SDO.contributor)
        ):
            self.G.remove((s, DC.contributor, o))
            self.G.remove((s, SDO.contributor, o))
            self.G.add((s, DCTERMS.contributor, o))

        # publisher
        for s, o in chain(
                self.G.subject_objects(DC.publisher),
                self.G.subject_objects(SDO.publisher)
        ):
            self.G.remove((s, DC.publisher, o))
            self.G.remove((s, SDO.publisher, o))
            self.G.add((s, DCTERMS.publisher, o))

    def _extract_metadata(self):
        if len(self.CLASSES.keys()) > 0:
            self.METADATA["has_classes"] = True

        self.METADATA["has_ops"] = False
        self.METADATA["has_fps"] = False
        self.METADATA["has_dps"] = False
        self.METADATA["has_aps"] = False
        self.METADATA["has_ps"] = False

        if len(self.NAMED_INDIVIDUALS.keys()) > 0:
            self.METADATA["has_nis"] = True

        for k, v in self.PROPERTIES.items():
            if v.get("prop_type") == "op":
                self.METADATA["has_ops"] = True
            if v.get("prop_type") == "fp":
                self.METADATA["has_fps"] = True
            if v.get("prop_type") == "dp":
                self.METADATA["has_dps"] = True
            if v.get("prop_type") == "ap":
                self.METADATA["has_aps"] = True
            if v.get("prop_type") == "p":
                self.METADATA["has_ps"] = True

        s_str = None
        self.METADATA["imports"] = set()
        self.METADATA["creators"] = set()
        self.METADATA["contributors"] = set()
        self.METADATA["publishers"] = set()
        self.METADATA["editors"] = set()
        self.METADATA["funders"] = set()
        self.METADATA["translators"] = set()
        for s in self.G.subjects(predicate=RDF.type, object=OWL.Ontology):
            s_str = str(s)  # this is the Ontology's URI
            self.METADATA["uri"] = s_str

            for p, o in self.G.predicate_objects(subject=s):
                if p == OWL.imports:
                    self.METADATA["imports"].add(self._make_formatted_uri(o))

                if p == DCTERMS.title:
                    self.METADATA["title"] = str(o)

                if p == DCTERMS.description:
                    if self.outputformat == "md":
                        self.METADATA["description"] = str(o)
                    elif self.outputformat == "adoc":
                        self.METADATA["description"] = str(o)
                    else:
                        self.METADATA["description"] = markdown.markdown(str(o))

                if p == SKOS.historyNote:
                    if self.outputformat == "md":
                        self.METADATA["historyNote"] = str(o)
                    elif self.outputformat == "adoc":
                        self.METADATA["historyNote"] = str(o)
                    else:
                        self.METADATA["historyNote"] = markdown.markdown(str(o))

                # dates
                if p in [DCTERMS.created, DCTERMS.modified, DCTERMS.issued]:
                    date_type = p.split("/")[-1]
                    self.METADATA[date_type] = str(o)

                if p == DCTERMS.source:
                    if str(o).startswith('http'):
                        self.METADATA["source"] = self._make_formatted_uri(o)
                    else:
                        self.METADATA["source"] = str(o)

                if p == OWL.versionIRI:
                    self.METADATA["versionIRI"] = self._make_formatted_uri(o)

                if p == OWL.versionInfo:
                    self.METADATA["versionInfo"] = str(o)

                if p == URIRef("http://purl.org/vocab/vann/preferredNamespacePrefix"):
                    self.METADATA["preferredNamespacePrefix"] = str(o)

                if p == URIRef("http://purl.org/vocab/vann/preferredNamespaceUri"):
                    self.METADATA["preferredNamespaceUri"] = str(o)

                if p == DCTERMS.license:
                    self.METADATA["license"] = (
                        self._make_formatted_uri(o)
                        if str(o).startswith("http")
                        else str(o)
                    )

                if p == DCTERMS.rights:
                    self.METADATA["rights"] = (
                        str(o)
                            .replace("Copyright", "&copy;")
                            .replace("copyright", "&copy;")
                            .replace("(c)", "&copy;")
                    )

                # Agents
                if p in [
                    DCTERMS.creator, DCTERMS.contributor, DCTERMS.publisher, SDO.editor, SDO.funder, SDO.translator
                ]:
                    agent_type = p.split("/")[-1] + "s"
                    if type(o) == Literal:
                        self.METADATA[agent_type].add(str(o))
                    else:  # Blank Node or URI
                        self.METADATA[agent_type].add(self._make_agent(o))

                if p == PROV.wasGeneratedBy:
                    for o2 in self.G.objects(subject=o, predicate=DOAP.repository):
                        self.METADATA["repository"] = self._make_formatted_uri(o2)

                if p == SDO.codeRepository:
                    self.METADATA["repository"] = self._make_formatted_uri(o)

            if self.METADATA.get("title") is None:
                self.METADATA["title"] = "{no title found}"
                # raise ValueError(
                #     "Your ontology does not indicate any form of label or title. "
                #     "You must declare one of the following for your ontology: rdfs:label, dct:title, skos:prefLabel"
                # )

        if s_str is None:
            raise Exception(
                "Your RDF file does not define an ontology. "
                "It must contains a declaration such as <...> rdf:type owl:Ontology ."
            )

    def _extract_classes_uris(self):
        classes = []
        for s in self.G.subjects(predicate=RDF.type, object=RDFS.Class):
            # ignore blank nodes for things like [ owl:unionOf ( ... ) ]
            if type(s) == BNode:
                pass
            else:
                classes.append(str(s))

        for p in sorted(classes):
            self.CLASSES[p] = {}

    def _extract_classes(self):
        for cls in self.CLASSES.keys():
            s = URIRef(cls)
            # create Python dict for each class
            self.CLASSES[cls] = {
                "iri": cls
            }

            # basic class properties
            self.CLASSES[cls]["title"] = None
            self.CLASSES[cls]["description"] = None
            self.CLASSES[cls]["scopeNote"] = None
            self.CLASSES[cls]["examples"] = []
            self.CLASSES[cls]["isDefinedBy"] = None
            self.CLASSES[cls]["source"] = None

            for p, o in self.G.predicate_objects(subject=s):
                if p == DCTERMS.title:
                    self.CLASSES[cls]["title"] = str(o)

                if p == DCTERMS.description:
                    if self.outputformat == "md":
                        self.CLASSES[cls]["description"] = str(o)
                    elif self.outputformat == "adoc":
                        self.CLASSES[cls]["description"] = str(o)
                    else:
                        self.CLASSES[cls]["description"] = markdown.markdown(str(o))

                if p == SKOS.scopeNote:
                    if self.outputformat == "md":
                        self.CLASSES[cls]["scopeNote"] = str(o)
                    elif self.outputformat == "adoc":
                        self.CLASSES[cls]["scopeNote"] = str(o)
                    else:
                        self.CLASSES[cls]["scopeNote"] = markdown.markdown(str(o))

                if p == SKOS.example:
                    self.CLASSES[cls]["examples"].append(self._make_example(o))

                if p == RDFS.isDefinedBy:
                    self.CLASSES[cls]["isDefinedBy"] = str(o)

                if p == DCTERMS.source or p == DC.source:
                    if str(o).startswith('http'):
                        self.CLASSES[cls]["source"] = self._make_formatted_uri(o)
                    else:
                        self.CLASSES[cls]["source"] = str(o)

            # patch title from URI if we haven't got one
            if self.CLASSES[cls]["title"] is None:
                self.CLASSES[cls]["title"] = self._make_title_from_uri(cls)

            # make fid
            self.CLASSES[cls]["fid"] = self._make_fid(self.CLASSES[cls]["title"], cls)

            # equivalent classes
            equivalent_classes = []
            for o in self.G.objects(subject=s, predicate=OWL.equivalentClass):
                if type(o) != BNode:
                    equivalent_classes.append(
                        self._get_curie(str(o))
                    )  # ranges that are just classes
                else:
                    # equivalent classes collections (unionOf | intersectionOf
                    q = """
                        PREFIX owl:  <http://www.w3.org/2002/07/owl#>
                        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

                        SELECT ?col_type ?col_member
                        WHERE {{
                            <{}> owl:equivalentClass ?eq .
                            ?eq owl:unionOf|owl:intersectionOf ?collection .
                            ?eq ?col_type ?collection .
                            ?collection rdf:rest*/rdf:first ?col_member .
                        }}
                    """.format(
                        s
                    )
                    collection_type = None
                    collection_members = []
                    for r in self.G.query(q):
                        collection_type = self._get_curie(str(r.col_type))
                        collection_members.append(self._get_curie(str(r.col_member)))
                    equivalent_classes.append((collection_type, collection_members))
            self.CLASSES[cls]["equivalents"] = equivalent_classes

            # super classes
            supers = []
            restrictions = []
            for o in self.G.objects(subject=s, predicate=RDFS.subClassOf):
                if (o, RDF.type, OWL.Restriction) not in self.G:
                    if type(o) != BNode:
                        supers.append(str(o))  # supers that are just classes
                    else:
                        # super collections (unionOf | intersectionOf
                        q = """
                            PREFIX owl:  <http://www.w3.org/2002/07/owl#>
                            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

                            SELECT ?col_type ?col_member
                            WHERE {{
                                <{}> rdfs:subClassOf ?sup .
                                ?sup owl:unionOf|owl:intersectionOf ?collection .
                                ?sup ?col_type ?collection .
                                ?collection rdf:rest*/rdf:first ?col_member .
                            }}
                        """.format(
                            s
                        )
                        collection_type = None
                        collection_members = []
                        for r in self.G.query(q):
                            collection_type = self._get_curie(str(r.col_type))
                            collection_members.append(str(r.col_member))
                        supers.append((collection_type, collection_members))
                else:
                    restrictions.append(o)

            self.CLASSES[cls]["supers"] = supers
            self.CLASSES[cls]["restrictions"] = restrictions

            # sub classes
            subs = []
            for o in self.G.subjects(predicate=RDFS.subClassOf, object=s):
                if type(o) != BNode:
                    subs.append(str(o))
                else:
                    # sub classes collections (unionOf | intersectionOf
                    q = """
                        PREFIX owl:  <http://www.w3.org/2002/07/owl#>
                        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

                        SELECT ?col_type ?col_member
                        WHERE {{
                            ?sub rdfs:subClassOf <{}> .
                            ?sub owl:unionOf|owl:intersectionOf ?collection .
                            ?sub ?col_type ?collection .
                            ?collection rdf:rest*/rdf:first ?col_member .
                        }}
                    """.format(
                        s
                    )
                    collection_type = None
                    collection_members = []
                    for r in self.G.query(q):
                        collection_type = self._get_curie(str(r.col_type))
                        collection_members.append(self._get_curie(str(r.col_member)))
                    subs.append((collection_type, collection_members))
            self.CLASSES[cls]["subs"] = subs

            in_domain_of = []
            for o in self.G.subjects(predicate=RDFS.domain, object=s):
                in_domain_of.append(str(o))
            self.CLASSES[cls]["in_domain_of"] = in_domain_of

            in_domain_includes_of = []
            for o in self.G.subjects(predicate=SDO.domainIncludes, object=s):
                in_domain_includes_of.append(str(o))
            self.CLASSES[cls]["in_domain_includes_of"] = in_domain_includes_of

            in_range_of = []
            for o in self.G.subjects(predicate=RDFS.range, object=s):
                in_range_of.append(str(o))
            self.CLASSES[cls]["in_range_of"] = in_range_of

            in_range_includes_of = []
            for o in self.G.subjects(predicate=SDO.rangeIncludes, object=s):
                in_range_includes_of.append(str(o))
            self.CLASSES[cls]["in_range_includes_of"] = in_range_includes_of

            # TODO: cater for Named Individuals of this class - "has members"
            has_members = []
            for o in self.G.subjects(predicate=RDF.type, object=s):
                has_members.append(str(o))
            self.CLASSES[cls]["has_members"] = has_members

        # # sort properties by title
        # x = sorted([(k, v) for k, v in classes.items()], key=lambda tup: tup[1]['title'])
        # y = collections.OrderedDict()
        # for n in x:
        #     y[n[0]] = n[1]
        #
        # return y

    def _extract_properties_uris(self):
        properties = []
        for s in self.G.subjects(predicate=RDF.type, object=RDF.Property):
            properties.append(str(s))

        for p in sorted(properties):
            self.PROPERTIES[p] = {}

    def _extract_properties(self):
        for prop in self.PROPERTIES.keys():
            s = URIRef(prop)
            # property type
            if (s, RDF.type, OWL.FunctionalProperty) in self.G:
                self.PROPERTIES[prop]["prop_type"] = "fp"
            elif (s, RDF.type, OWL.ObjectProperty) in self.G:
                self.PROPERTIES[prop]["prop_type"] = "op"
            elif (s, RDF.type, OWL.DatatypeProperty) in self.G:
                self.PROPERTIES[prop]["prop_type"] = "dp"
            elif (s, RDF.type, OWL.AnnotationProperty) in self.G:
                self.PROPERTIES[prop]["prop_type"] = "ap"
            else:
                self.PROPERTIES[prop]["prop_type"] = "p"

            self.PROPERTIES[prop]["title"] = None
            self.PROPERTIES[prop]["description"] = None
            self.PROPERTIES[prop]["scopeNote"] = None
            self.PROPERTIES[prop]["examples"] = []
            self.PROPERTIES[prop]["isDefinedBy"] = None
            self.PROPERTIES[prop]["source"] = None
            self.PROPERTIES[prop]["supers"] = []
            self.PROPERTIES[prop]["subs"] = []
            self.PROPERTIES[prop]["equivs"] = []
            self.PROPERTIES[prop]["invs"] = []
            self.PROPERTIES[prop]["domains"] = []
            self.PROPERTIES[prop]["domainIncludes"] = []
            self.PROPERTIES[prop]["ranges"] = []
            self.PROPERTIES[prop]["rangeIncludes"] = []

            for p, o in self.G.predicate_objects(subject=s):
                if p == DCTERMS.title:
                    self.PROPERTIES[prop]["title"] = str(o)

                if p == DCTERMS.description:
                    if self.outputformat == "md":
                        self.PROPERTIES[prop]["description"] = str(o)
                    elif self.outputformat == "adoc":
                        self.PROPERTIES[prop]["description"] = str(o)
                    else:
                        self.PROPERTIES[prop]["description"] = markdown.markdown(str(o))

                if p == SKOS.scopeNote:
                    if self.outputformat == "md":
                        self.PROPERTIES[prop]["scopeNote"] = str(o)
                    elif self.outputformat == "adoc":
                        self.PROPERTIES[prop]["scopeNote"] = str(o)
                    else:
                        self.PROPERTIES[prop]["scopeNote"] = markdown.markdown(str(o))

                if p == SKOS.example:
                    self.PROPERTIES[prop]["examples"].append(self._make_example(o))

                if p == RDFS.isDefinedBy:
                    self.PROPERTIES[prop]["isDefinedBy"] = str(o)

                if p == DCTERMS.source or p == DC.source:
                    if str(o).startswith('http'):
                        self.PROPERTIES[prop]["source"] = self._make_formatted_uri(o)
                    else:
                        self.PROPERTIES[prop]["source"] = str(o)

            # patch title from URI if we haven't got one
            if self.PROPERTIES[prop]["title"] is None:
                self.PROPERTIES[prop]["title"] = self._make_title_from_uri(prop)

            # make fid
            self.PROPERTIES[prop]["fid"] = self._make_fid(
                self.PROPERTIES[prop]["title"], prop
            )

            # super properties
            for o in self.G.objects(subject=s, predicate=RDFS.subPropertyOf):
                if type(o) != BNode:
                    self.PROPERTIES[prop]["supers"].append(str(o))  # self._make_uri_html

            # sub properties
            for o in self.G.subjects(predicate=RDFS.subPropertyOf, object=s):
                if type(o) != BNode:
                    self.PROPERTIES[prop]["subs"].append(str(o))

            # equivalent properties
            for o in self.G.objects(subject=s, predicate=OWL.equivalentProperty):
                if type(o) != BNode:
                    self.PROPERTIES[prop]["equivs"].append(str(o))

            # inverse properties
            for o in self.G.objects(subject=s, predicate=OWL.inverseOf):
                if type(o) != BNode:
                    self.PROPERTIES[prop]["invs"].append(str(o))

            # domains
            for o in self.G.objects(subject=s, predicate=RDFS.domain):
                if type(o) != BNode:
                    self.PROPERTIES[prop]["domains"].append(str(o))  # domains that are just classes
                else:
                    # domain collections (unionOf | intersectionOf
                    q = """
                        PREFIX owl:  <http://www.w3.org/2002/07/owl#>
                        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

                        SELECT ?col_type ?col_member
                        WHERE {{
                            <{}> rdfs:domain ?domain .
                            ?domain owl:unionOf|owl:intersectionOf ?collection .
                            ?domain ?col_type ?collection .
                            ?collection rdf:rest*/rdf:first ?col_member .
                        }}
                    """.format(
                        s
                    )
                    collection_type = None
                    collection_members = []
                    for r in self.G.query(q):
                        collection_type = self._get_curie(str(r.col_type))
                        collection_members.append(str(r.col_member))
                    self.PROPERTIES[prop]["domains"].append((collection_type, collection_members))

            # domainIncludes
            for o in self.G.objects(subject=s, predicate=SDO.domainIncludes):
                if type(o) != BNode:
                    self.PROPERTIES[prop]["domainIncludes"].append(
                        str(o)
                    )  # domainIncludes that are just classes
                else:
                    # domainIncludes collections (unionOf | intersectionOf
                    q = """
                        PREFIX owl:  <http://www.w3.org/2002/07/owl#>
                        PREFIX sdo: <https://schema.org/>

                        SELECT ?col_type ?col_member
                        WHERE {{
                            <{}> sdo:domainIncludes ?domainIncludes .
                            ?domainIncludes owl:unionOf|owl:intersectionOf ?collection .
                            ?domainIncludes ?col_type ?collection .
                            ?collection rdf:rest*/rdf:first ?col_member .
                        }}
                    """.format(
                        s
                    )
                    collection_type = None
                    collection_members = []
                    for r in self.G.query(q):
                        collection_type = self._get_curie(str(r.col_type))
                        collection_members.append(str(r.col_member))
                    self.PROPERTIES[prop]["domainIncludes"].append((collection_type, collection_members))

            # ranges
            for o in self.G.objects(subject=s, predicate=RDFS.range):
                if type(o) != BNode:
                    #self.PROPERTIES[prop]["ranges"].append(self._make_formatted_uri(o, type="c"))
                    #self.PROPERTIES[prop]["ranges"].append(self._build_link(uri=o, type="c", source="ranges"))  # ranges that are just classes
                    self.PROPERTIES[prop]["ranges"].append(o)
                else:
                    # range collections (unionOf | intersectionOf)
                    q = """
                        PREFIX owl:  <http://www.w3.org/2002/07/owl#>
                        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

                        SELECT ?col_type ?col_member
                        WHERE {{
                            <{}> rdfs:range ?range .
                            ?range owl:unionOf|owl:intersectionOf ?collection .
                            ?range ?col_type ?collection .
                            ?collection rdf:rest*/rdf:first ?col_member .
                        }}
                    """.format(
                        s
                    )
                    collection_type = None
                    collection_members = []
                    for r in self.G.query(q):
                        collection_type = self._get_curie(str(r.col_type))
                        collection_members.append(str(r.col_member))
                    self.PROPERTIES[prop]["ranges"].append((collection_type, collection_members))

            # rangeIncludes
            for o in self.G.objects(subject=s, predicate=SDO.rangeIncludes):
                if type(o) != BNode:
                    self.PROPERTIES[prop]["rangeIncludes"].append(str(o))  # rangeIncludes that are just classes
                else:
                    # rangeIncludes collections (unionOf | intersectionOf
                    q = """
                        PREFIX owl:  <http://www.w3.org/2002/07/owl#>
                        PREFIX sdo: <https://schema.org/>

                        SELECT ?col_type ?col_member
                        WHERE {{
                            <{}> sdo:rangeIncludes ?rangeIncludes .
                            ?rangeIncludes owl:unionOf|owl:intersectionOf ?collection .
                            ?rangeIncludes ?col_type ?collection .
                            ?collection rdf:rest*/rdf:first ?col_member .
                        }}
                    """.format(
                        s
                    )
                    collection_type = None
                    collection_members = []
                    for r in self.G.query(q):
                        collection_type = self._get_curie(str(r.col_type))
                        collection_members.append(str(r.col_member))
                    self.PROPERTIES[prop]["rangeIncludes"].append((collection_type, collection_members))

            # TODO: cater for sub property chains

        # # sort properties by title
        # x = sorted([(k, v) for k, v in self.PROPERTIES.items()], key=lambda tup: tup[1]['title'])
        # y = collections.OrderedDict()
        # for n in x:
        #     y[n[0]] = n[1]
        #
        # return y

    def _extract_named_individuals_uris(self):
        named_individuals = []
        for s in self.G.subjects(predicate=RDF.type, object=OWL.NamedIndividual):
            named_individuals.append(str(s))

        for ni in sorted(named_individuals):
            self.NAMED_INDIVIDUALS[ni] = {}

    def _extract_named_individuals(self):
        for ni in self.NAMED_INDIVIDUALS.keys():
            if ni.startswith("http"):
                s = URIRef(ni)
            else:
                s = BNode(ni)
            # create Python dict for each NI
            self.NAMED_INDIVIDUALS[ni] = {}

            # basic NI properties
            self.NAMED_INDIVIDUALS[ni]["classes"] = set()
            self.NAMED_INDIVIDUALS[ni]["title"] = None
            self.NAMED_INDIVIDUALS[ni]["description"] = None
            self.NAMED_INDIVIDUALS[ni]["isDefinedBy"] = None
            self.NAMED_INDIVIDUALS[ni]["source"] = None
            self.NAMED_INDIVIDUALS[ni]["seeAlso"] = None
            self.NAMED_INDIVIDUALS[ni]["sameAs"] = None

            for p, o in self.G.predicate_objects(subject=s):
                # list all the other classes of this NI
                if p == RDF.type:
                    if o != OWL.NamedIndividual:
                        self.NAMED_INDIVIDUALS[ni]["classes"].add(self._make_formatted_uri(o))

                if p == DCTERMS.title:
                    self.NAMED_INDIVIDUALS[ni]["title"] = str(o)

                if p == DCTERMS.description:
                    self.NAMED_INDIVIDUALS[ni]["description"] = str(o)

                if p == RDFS.isDefinedBy:
                    self.NAMED_INDIVIDUALS[ni]["isDefinedBy"] = str(o)

                if p == DCTERMS.source or p == DC.source:
                    if str(o).startswith('http'):
                        self.NAMED_INDIVIDUALS[ni]["source"] = self._make_formatted_uri(o)
                    else:
                        self.NAMED_INDIVIDUALS[ni]["source"] = str(o)

                if p == RDFS.seeAlso:
                    self.NAMED_INDIVIDUALS[ni]["seeAlso"] = self._make_formatted_uri(o)

                if p == OWL.sameAs:
                    self.NAMED_INDIVIDUALS[ni]["sameAs"] = self._make_formatted_uri(o)

            # patch title from URI if we haven't got one
            if self.NAMED_INDIVIDUALS[ni].get("title") is None:
                self.NAMED_INDIVIDUALS[ni]["title"] = self._make_title_from_uri(ni)

            # make fid
            self.NAMED_INDIVIDUALS[ni]["fid"] = self._make_fid(self.NAMED_INDIVIDUALS[ni]["title"], ni)

    def _make_metadata(self):
        return self._load_template("metadata." + self.outputformat).render(
            imports=sorted(self.METADATA["imports"]),
            title=self.METADATA.get("title"),
            uri=self.METADATA.get("uri"),
            version_uri=self.METADATA.get("versionIRI"),
            publishers=sorted(self.METADATA["publishers"]),
            creators=sorted(self.METADATA["creators"]),
            contributors=sorted(self.METADATA["contributors"]),
            created=self.METADATA.get("created"),  # TODO: auto-detect format
            modified=self.METADATA.get("modified"),
            issued=self.METADATA.get("issued"),
            source=self.METADATA.get("source"),
            description=self.METADATA.get("description"),
            historyNote=self.METADATA.get("historyNote"),
            version_info=self.METADATA.get("versionInfo"),
            license=self.METADATA.get("license"),
            rights=self.METADATA.get("rights"),
            repository=self.METADATA.get("repository"),
            ont_rdf=self._make_source_file_link(),
            has_classes=self.METADATA.get("has_classes"),
            has_ops=self.METADATA.get("has_ops"),
            has_fps=self.METADATA.get("has_fps"),
            has_dps=self.METADATA.get("has_dps"),
            has_aps=self.METADATA.get("has_aps"),
            has_ps=self.METADATA.get("has_ps"),
            has_nis=self.METADATA.get("has_nis"),
        )

    def _make_class(self, uri, class_):
        class_template = self._load_template("class." + self.outputformat)
        # handling Markdown formatting within a table
        if self.outputformat == "md":
            desc = class_["description"].replace("\n", " ") if class_.get("description") is not None else None
        elif self.outputformat == "adoc":
            desc = class_["description"]
        else:
            desc = class_["description"]

        return class_template.render(
            uri=uri,
            fid=class_["fid"],
            title=class_["title"],
            description=desc,
            supers=class_["supers"],
            restrictions=class_["restrictions"],
            scopeNote=class_["scopeNote"],
            examples=class_["examples"],
            is_defined_by=class_["isDefinedBy"],
            source=class_["source"],
            subs=class_["subs"],
            in_domain_of=class_["in_domain_of"],
            in_domain_includes_of=class_["in_domain_includes_of"],
            in_range_of=class_["in_range_of"],
            in_range_includes_of=class_["in_range_includes_of"],
            has_members=class_["has_members"]
        )

    def _make_class2(self, class2):
        # handling Markdown formatting within a table
        if self.outputformat == "md":
            desc = class2[1].get("description").replace("\n", " ") \
                if class2[1].get("description") is not None else None
        elif self.outputformat == "adoc":
            desc = class2[1].get("description")
        else:
            desc = class2[1].get("description")

        return self._load_template("class." + self.outputformat).render(
            uri=class2[0],
            fid=class2[1].get("fid"),
            title=class2[1].get("title"),
            description=desc,
        )


    def _make_classes(self):
        # make all the individual Classes
        classes_list = []
        for k, v in self.CLASSES.items():
            classes_list.append(self._make_class(k, v))

        cl_instances = []

        for k, v in self.CLASSES.items():
            cl_instances.append(
                (
                    v["title"],
                    v["fid"],
                    self._make_class2((k, v)),
                )
            )

        # make the template for all Classes
        classes_template = self._load_template("classes." + self.outputformat)
        # add in Class index
        # fids = sorted(
        #     [(v.get("fid"), v.get("title")) for k, v in self.CLASSES.items()],
        #     key=lambda tup: tup[1],
        # )
        class_index = [f"<li>{self._make_formatted_uri(x)}</li>" for x in self.CLASSES.keys()]
        return classes_template.render(class_index=class_index, classes=classes_list, cl_instances=cl_instances, )

    def _make_property(self, property):
        # handling Markdown formatting within a table
        if self.outputformat == "md":
            desc = property[1].get("description").replace("\n", " ") \
                if property[1].get("description") is not None else None
        elif self.outputformat == "adoc":
            desc = property[1].get("description")
        else:
            desc = property[1].get("description")

        return self._load_template("property." + self.outputformat).render(
            uri=property[0],
            fid=property[1].get("fid"),
            property_type=property[1].get("prop_type"),
            title=property[1].get("title"),
            description=desc,
            scopeNote=property[1].get("scopeNote"),
            examples=property[1].get("examples"),
            is_defined_by=property[1].get("isDefinedBy"),
            source=property[1].get("source"),
            supers=property[1].get("supers"),
            subs=property[1].get("subs"),
            equivs=property[1].get("equivs"),
            invs=property[1].get("invs"),
            domains=property[1]["domains"],
            domainIncludes=property[1]["domainIncludes"],
            ranges=property[1]["ranges"],
            rangeIncludes=property[1]["rangeIncludes"],
        )

    def _make_properties(self):
        # make all properties, grouped by OWL type
        op_instances = []
        fp_instances = []
        dp_instances = []
        ap_instances = []
        p_instances = []

        for k, v in self.PROPERTIES.items():
            if v.get("prop_type") == "op":
                op_instances.append(
                    (
                        v["title"],
                        v["fid"],
                        self._make_property((k, v)),
                    )
                )
            elif v.get("prop_type") == "fp":
                fp_instances.append(
                    (
                        v["title"],
                        v["fid"],
                        self._make_property((k, v)),
                    )
                )
            elif v.get("prop_type") == "dp":
                dp_instances.append(
                    (
                        v["title"],
                        v["fid"],
                        self._make_property((k, v)),
                    )
                )
            elif v.get("prop_type") == "ap":
                ap_instances.append(
                    (
                        v["title"],
                        v["fid"],
                        self._make_property((k, v)),
                    )
                )
            elif v.get("prop_type") == "p":
                p_instances.append(
                    (
                        v["title"],
                        v["fid"],
                        self._make_property((k, v)),
                    )
                )

        # make the template for all properties
        return self._load_template("properties." + self.outputformat).render(
            op_instances=op_instances,
            fp_instances=fp_instances,
            dp_instances=dp_instances,
            ap_instances=ap_instances,
            p_instances=p_instances,
        )

    def _make_named_individual(self, named_individual):
        return self._load_template("named_individual." + self.outputformat).render(
            uri=named_individual[0],
            fid=named_individual[1].get("fid"),
            classes=named_individual[1].get("classes"),
            title=named_individual[1].get("title"),
            description=named_individual[1].get("description"),
            is_defined_by=named_individual[1].get("isDefinedBy"),
            source=named_individual[1].get("source"),
            see_also=named_individual[1].get("seeAlso"),
            same_as=named_individual[1].get("sameAs")
        )

    def _make_named_individuals(self):
        named_individuals_list = []
        for k, v in self.NAMED_INDIVIDUALS.items():
            named_individuals_list.append(
                self._make_named_individual((k, v))
            )

        # add in NIs index
        fids = []
        for k, v in self.NAMED_INDIVIDUALS.items():
            if v.get("fid") is not None:  # ensure BNodes not added
                fids.append((v.get("fid"), v.get("title")))
        fids = sorted(fids, key=lambda tup: tup[1])
        return self._load_template("named_individuals." + self.outputformat).render(
            fids=fids,
            named_individuals=named_individuals_list
        )

    def _make_code(self, field_var) -> str:
        """Returns the given field_var as code (<code>) in this instances' output format"""
        if self.outputformat == "md":
            escaped_var = field_var.rstrip().replace("\t", "    ").split("\n")
            eg2 = ""
            for line in escaped_var:
                eg2 += f"`{line}` <br /> "
            field_var = eg2
            return field_var
        if self.outputformat == "adoc":
            return f"....\n{field_var}\n....\n\n"
        else:
            escaped_var = field_var.replace("<", "&lt;").replace(">", "&gt;")
            return f"<pre>{escaped_var}</pre>"

    def _make_resource_descriptor_example(self, rd: Union[URIRef, BNode]) -> str:
        code_formats = [
            "text/turtle",
            "text/n3",
            "application/ld+json",
            "application/json",
            "application/rdf+xml",
            "application/xml",
        ]
        markup_formats = [
            "text/html",
            "text/markdown",
            "text/asciidoc",
            # "text/x-rst"
        ]
        is_code = False
        is_markup = False
        artifact = None
        format = None
        conforms_to = None
        for p, o in self.G.predicate_objects(subject=rd):
            if p == DCTERMS["format"]:
                format = str(o)
                if format in code_formats:
                    is_code = True
                elif format in markup_formats:
                    is_markup = True
            elif p == DCTERMS.conformsTo:
                conforms_to = str(o)
            elif p == PROF.hasArtifact:
                artifact = str(o)

        eg = ""
        if is_code:
            eg = self._make_code(artifact)
        elif is_markup:
            if format == "text/html" and self.outputformat in ["html", "md"]:
                eg = artifact
            elif format == "text/html" and self.outputformat == "adoc":
                eg = f"+++{artifact}+++\n&nbsp;"
            elif format == "text/markdown" and self.outputformat == "md":
                eg = artifact
            elif format == "text/markdown" and self.outputformat == "adoc":
                eg = f"+++{markdown.markdown(artifact)}+++\n&nbsp;"
            elif format == "text/markdown" and self.outputformat == "html":
                eg = markdown.markdown(artifact)
            elif format == "text/asciidoc" and self.outputformat == "html":  # TODO: test ASCIIDOC rendering in HTML
                eg = markdown.markdown(artifact)
        else:
            eg = self._make_code(artifact)

        if conforms_to is not None:
            if self.outputformat == "html":
                return f"<div style=\"border:solid 1px lightgrey; padding:5px;\">{eg}<br />Conforms to: <a href=\"{conforms_to}\">{conforms_to}</a></div>"
            elif self.outputformat == "md":
                return f"{eg}\n\nConforms to: [{conforms_to}]({conforms_to})"
            elif self.outputformat == "adoc":
                return f"{eg}\n\nConforms to: link:{conforms_to}[{conforms_to}]"
        else:
            return eg

    def _make_example(self, o: Union[URIRef, BNode, Literal]) -> str:
        """Returns an HTML / Markdown / ASCIIDOC string of this Class / Property's example, formatted according
        to this OntDoc instance's outputformat instance variable. All content needed is extracted from this
        instance's graph (self.G)"""

        o_str = str(o)

        # check to see if it is an image, if so, render it
        # could be a URIRef or Literal
        if re.findall(r"(.png|.jpg|.tiff|.gif|.webp|.pdf|.svg)#?", o_str):
            if self.outputformat == "md":
                return f"![]({o_str}) "
            if self.outputformat == "adoc":
                return f"image::{o_str}[]"
            else:
                return f"<img src=\"{o_str}\" />"

        # check to see if this is a hyperlink only, if so, render a link
        # could be a URIRef or Literal
        if re.match(r"http", o_str):
            # check to see if the hyperlink is to an object in this ont
            local = False
            for p2, o2 in self.G.predicate_objects(subject=o):
                local = True

            if local:
                return self._make_resource_descriptor_example(o)

            if self.outputformat == "md":
                return f"[{o_str}]({o_str}) "
            elif self.outputformat == "adoc":
                return f"{o_str} "
            else:  # self.outputformat == "md":
                return f"<a href=\"{o_str}\">{o_str}</a>"

        # check to see if it's a BN for further handling or a Literal
        if type(o) == BNode:
            # it must be a Resource Descriptor BN
            return self._make_resource_descriptor_example(o)
        elif type(o) == Literal:
            # handle any declared datatypes (within rdf:HTML, rdf:XMLLiteral & rdf:JSON)
            if o.datatype == RDF.HTML:
                if self.outputformat == "md":
                    return str(o)
                elif self.outputformat == "adoc":
                    return f"+++{str(o)}+++\n&nbsp;"
                else:  # self.outputformat == "html":
                    return str(o)
            if o.datatype == RDF.XMLLiteral or RDF.JSON:
                return self._make_code(o)

        # fall-back: just print out a <code>-formatted literal
        return self._make_code(o)

    def _make_document(self):
        css = None
        if self.outputformat == "html":
            if self.include_css:
                css = open(path.join(STYLE_DIR, "pylode.css")).read()

        return self._load_template("document." + self.outputformat).render(
            schemaorg=self._make_schemaorg_metadata(),  # only does something for the HTML templates
            title=self.METADATA["title"],
            metadata=self._make_metadata(),
            classes=self._make_classes(),
            properties=self._make_properties(),
            named_individuals=self._make_named_individuals(),
            default_namespace=self.METADATA["default_namespace"],
            namespaces=self._make_namespaces(),
            css=css,
            pylode_version=__version__
        )

    def _build_link(self, uri, type=None, source=None):
        if uri == None:
            return self._make_formatted_uri(uri, type=type)

        found = 0
        link = ""
        for k, v in self.PROPERTIES.items():
            if k == uri:
                title = v.get("title")
                link = "<a href=#" + title.replace(" ", "") + ">" + v.get("title") + "</a>"
                found = 1
                break
        if found == 0:
            for k, v in self.CLASSES.items():
                if k == uri:
                    title = v.get("title")
                    link = "<a href=#" + title.replace(" ", "") + ">" + v.get("title") + "</a>"
                    found = 1
                    break
        if found == 0:
            link = self._make_formatted_uri(uri, type=type)

        return link

    def generate_document(self):
        # expand the graph using pre-defined rules to make querying easier (poor man's inference)
        self._expand_graph()
        # get all the namespaces using several methods
        self._extract_namespaces()
        # get the default namespace
        self._get_default_namespace()
        # get the IDs (URIs) of all properties -> self.PROPERTIES
        self._extract_properties_uris()
        # get the IDs (URIs) of all classes -> CLASSES
        self._extract_classes_uris()
        # get the IDs (URIs) of all Named Individuals -> NAMED_INDIVIDUALS
        self._extract_named_individuals_uris()
        # get all the properties' details
        self._extract_properties()
        # get all the classes' details
        self._extract_classes()
        # get all the Named Individuals' details
        self._extract_named_individuals()
        # get the ontology's metadata
        self._extract_metadata()
        # create fragment URIs for default namespace classes & properties
        # for each CURIE, if it's in the default namespace, i.e. this ontology, use its fragment URI

        # crosslinking properties
        for uri, prop in self.PROPERTIES.items():
            html = []
            for p in prop["supers"]:
                prop_type = (
                    self.PROPERTIES.get(p).get("prop_type")
                    if self.PROPERTIES.get(p)
                    else None
                )
                #html.append(self._make_formatted_uri(p, type=prop_type))
                html.append(self._build_link(uri=p, type=prop_type))
            self.PROPERTIES[uri]["supers"] = natsorted(html)

            html = []
            for p in prop["subs"]:
                prop_type = (
                    self.PROPERTIES.get(p).get("prop_type")
                    if self.PROPERTIES.get(p)
                    else None
                )
                #html.append(self._make_formatted_uri(p, type=prop_type))
                html.append(self._build_link(uri=p, type=prop_type))
            self.PROPERTIES[uri]["subs"] = natsorted(html)

            html = []
            for p in prop["equivs"]:
                prop_type = (
                    self.PROPERTIES.get(p).get("prop_type")
                    if self.PROPERTIES.get(p)
                    else None
                )
                #html.append(self._make_formatted_uri(p, type=prop_type))
                html.append(self._build_link(uri=p, type=prop_type, source="equivs"))
            self.PROPERTIES[uri]["equivs"] = natsorted(html)

            html = []
            for p in prop["invs"]:
                prop_type = (
                    self.PROPERTIES.get(p).get("prop_type")
                    if self.PROPERTIES.get(p)
                    else None
                )
                #html.append(self._make_formatted_uri(p, type=prop_type))
                html.append(self._build_link(uri=p, type=prop_type, source="equivs"))
            self.PROPERTIES[uri]["invs"] = natsorted(html)

            html = []
            for d in prop["domains"]:
                if type(d) == tuple:
                    html.append(self._make_collection_class_html(d[0], d[1]))
                else:
                    #html.append(self._make_formatted_uri(d, type="c"))
                    html.append(self._build_link(uri=d, type="c", source="domains"))

            self.PROPERTIES[uri]["domains"] = natsorted(html)

            html = []
            for d in prop["domainIncludes"]:
                if type(d) == tuple:
                    for m in d[1]:
                        #html.append(self._make_formatted_uri(m, type="c"))
                        html.append(self._build_link(uri=m, type="c", source="domainIncludes"))
                else:
                    #html.append(self._make_formatted_uri(d, type="c"))
                    html.append(self._build_link(uri=d, type="c", source="domainIncludes"))
            self.PROPERTIES[uri]["domainIncludes"] = natsorted(html)

            html = []
            for d in prop["ranges"]:
                if type(d) == tuple:
                    for m in d[1]:
                        html.append(m)
                        #html.append(self._build_link(uri=m, source="ranges"))
                else:
                    html.append(self._build_link(uri=str(d), source="ranges")) #html.append(d) #http://purl.obolibrary.org/obo/GSSO_009994
            self.PROPERTIES[uri]["ranges"] = natsorted(html)

            html = []
            for d in prop["rangeIncludes"]:
                if type(d) == tuple:
                    for m in d[1]:
                        #html.append(self._make_formatted_uri(m, type="c"))
                        html.append(self._build_link(uri=m, type="c", source="rangeIncludes"))
                else:
                    #html.append(self._make_formatted_uri(d, type="c"))
                    html.append(self._build_link(uri=d, type="c", source="rangeIncludes"))
            self.PROPERTIES[uri]["rangeIncludes"] = natsorted(html)

        # crosslinking classes
        for uri, cls in self.CLASSES.items():
            html = []
            for d in cls["equivalents"]:
                if type(d) == tuple:
                    for m in d[1]:
                        #html.append(self._make_formatted_uri(m, type="c"))
                        html.append(self._build_link(uri=m, type="c", source="equivalents"))
                else:
                    #html.append(self._make_formatted_uri(d, type="c"))
                    html.append(self._build_link(uri=d, type="c", source="echivalents"))
            self.CLASSES[uri]["equivalents"] = natsorted(html)

            html = []
            for d in cls["supers"]:
                if type(d) == tuple:
                    html.append(self._make_collection_class_html(d[0], d[1]))
                else:
                    #html.append(self._make_formatted_uri(d, type="c"))
                    html.append(self._build_link(uri=d, type="c", source="supers"))
            self.CLASSES[uri]["supers"] = natsorted(html)

            html = []
            for d in cls["restrictions"]:
                html.append(self._make_restriction_html(uri, d))
            self.CLASSES[uri]["restrictions"] = natsorted(html)

            html = []
            for d in cls["subs"]:
                if type(d) == tuple:
                    for m in d[1]:
                        #html.append(self._make_formatted_uri(m, type="c"))
                        html.append(self._build_link(uri=m, type="c", source="subs"))
                else:
                    #html.append(self._make_formatted_uri(d, type="c"))
                    html.append(self._build_link(uri=d, type="c", source="subs"))
            self.CLASSES[uri]["subs"] = natsorted(html)

            html = []
            for p in cls["in_domain_of"]:
                prop_type = (
                    self.PROPERTIES.get(p).get("prop_type")
                    if self.PROPERTIES.get(p)
                    else None
                )
                #html.append(self._make_formatted_uri(p, type=prop_type))
                html.append(self._build_link(uri=p, type=prop_type, source="if_domain_of"))

            self.CLASSES[uri]["in_domain_of"] = natsorted(html)

            html = []
            for p in cls["in_domain_includes_of"]:
                prop_type = (
                    self.PROPERTIES.get(p).get("prop_type")
                    if self.PROPERTIES.get(p)
                    else None
                )
                #html.append(self._make_formatted_uri(p, type=prop_type))
                html.append(self._build_link(uri=p, type=prop_type, source="in_domain_includes_of"))
            self.CLASSES[uri]["in_domain_includes_of"] = natsorted(html)

            html = []
            for p in cls["in_range_of"]:
                prop_type = (
                    self.PROPERTIES.get(p).get("prop_type")
                    if self.PROPERTIES.get(p)
                    else None
                )
                #html.append(self._make_formatted_uri(p, type=prop_type))
                html.append(self._build_link(uri=p, type=prop_type, source="in_range_of"))
            self.CLASSES[uri]["in_range_of"] = natsorted(html)

            html = []
            for p in cls["in_range_includes_of"]:
                prop_type = (
                    self.PROPERTIES.get(p).get("prop_type")
                    if self.PROPERTIES.get(p)
                    else None
                )
                #html.append(self._make_formatted_uri(p, type=prop_type))
                html.append(self._build_link(uri=p, type=prop_type, source="in_range_includes_of"))
            self.CLASSES[uri]["in_range_includes_of"] = natsorted(html)

            html = []
            for p in cls["has_members"]:
                prop_type = (
                    self.PROPERTIES.get(p).get("prop_type")
                    if self.PROPERTIES.get(p)
                    else None
                )
                #html.append(self._make_formatted_uri(p, type=prop_type))
                html.append(self._build_link(uri=p, type=prop_type, source="has_members"))
            self.CLASSES[uri]["has_members"] = natsorted(html)

        return self._make_document()
