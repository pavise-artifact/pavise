// SPDX-License-Identifier: BSD-3-Clause
/* Copyright 2015-2019, Intel Corporation */

/*
 * ctree_map.c -- Crit-bit trie implementation
 */

#include <ex_common.h>
#include <assert.h>
#include <errno.h>
#include <stdlib.h>
#include <stdio.h>
#include "ctree_map.h"
#include "pavise_interface.h" //PAVISE_EDIT

// PAVISE_EDIT: example on how to time code segment
//#include <time.h>
//double time_spent_ctree_map_insert=0;

#define BIT_IS_SET(n, i) (!!((n) & (1ULL << (i))))

TOID_DECLARE(struct tree_map_node, CTREE_MAP_TYPE_OFFSET + 1);

struct tree_map_entry {
	uint64_t key;
	PMEMoid slot;
};

struct tree_map_node {
	int diff; /* most significant differing bit */
	struct tree_map_entry entries[2];
};

struct ctree_map {
	struct tree_map_entry root;
};

/*
 * find_crit_bit -- (internal) finds the most significant differing bit
 */
static int
find_crit_bit(uint64_t lhs, uint64_t rhs)
{
	return find_last_set_64(lhs ^ rhs);
}

/*
 * ctree_map_create -- allocates a new crit-bit tree instance
 */
int
ctree_map_create(PMEMobjpool *pop, TOID(struct ctree_map) *map, void *arg)
{
	int ret = 0;

	TX_BEGIN(pop) {
		pmemobj_tx_add_range_direct(map, sizeof(*map));
		*map = TX_ZNEW(struct ctree_map);
	} TX_ONABORT {
		ret = 1;
	} TX_END

	return ret;
}

/*
 * ctree_map_clear_node -- (internal) clears this node and its children
 */
static void
ctree_map_clear_node(PMEMoid p)
{
	if (OID_IS_NULL(p))
		return;

	if (OID_INSTANCEOF(p, struct tree_map_node)) {
		TOID(struct tree_map_node) node;
		TOID_ASSIGN(node, p);

		ctree_map_clear_node(D_RW(node)->entries[0].slot);
		ctree_map_clear_node(D_RW(node)->entries[1].slot);
	}

	pmemobj_tx_free(p);
}

/*
 * ctree_map_clear -- removes all elements from the map
 */
int
ctree_map_clear(PMEMobjpool *pop, TOID(struct ctree_map) map)
{
	TX_BEGIN(pop) {
		ctree_map_clear_node(D_RW(map)->root.slot);
		TX_ADD_FIELD(map, root);
		D_RW(map)->root.slot = OID_NULL;
	} TX_END

	return 0;
}

/*
 * ctree_map_destroy -- cleanups and frees crit-bit tree instance
 */
int
ctree_map_destroy(PMEMobjpool *pop, TOID(struct ctree_map) *map)
{
	int ret = 0;
	TX_BEGIN(pop) {
		ctree_map_clear(pop, *map);
		pmemobj_tx_add_range_direct(map, sizeof(*map));
		TX_FREE(*map);
		*map = TOID_NULL(struct ctree_map);
	} TX_ONABORT {
		ret = 1;
	} TX_END

	return ret;
}

/*
 * ctree_map_insert_leaf -- (internal) inserts a new leaf at the position
 */
static void
ctree_map_insert_leaf(struct tree_map_entry *p,
	struct tree_map_entry e, int diff)
{
	TOID(struct tree_map_node) new_node = TX_NEW(struct tree_map_node);
	D_RW(new_node)->diff = diff;

	int d = BIT_IS_SET(e.key, D_RO(new_node)->diff);

	/* insert the leaf at the direction based on the critical bit */
	D_RW(new_node)->entries[d] = e;

	/* find the appropriate position in the tree to insert the node */
	TOID(struct tree_map_node) node;
	while (pmemobj_direct(p->slot)!=0x300003c0550){  // PAVISE_EDIT. See ctree_map_insert for details
	//while (OID_INSTANCEOF(p->slot, struct tree_map_node)) {
		TOID_ASSIGN(node, p->slot);

		/* the critical bits have to be sorted */
		if (D_RO(node)->diff < D_RO(new_node)->diff)
			break;

		p = &D_RW(node)->entries[BIT_IS_SET(e.key, D_RO(node)->diff)];
	}

	/* insert the found destination in the other slot */
	D_RW(new_node)->entries[!d] = *p;
    //struct tree_map_entry tmp = {.key = 0, .slot = new_node.oid};
	//pmemobj_tx_add_range_direct(p, sizeof(*p)); //PAVISE_EDIT
	/*printf("executing memcpy, addr = %p\n", p);memcpy(p, &tmp, sizeof(struct tree_map_entry));*/p->key = 0;
	p->slot = new_node.oid;
}

/*
 * ctree_map_insert_new -- allocates a new object and inserts it into the tree
 */
int
ctree_map_insert_new(PMEMobjpool *pop, TOID(struct ctree_map) map,
		uint64_t key, size_t size, unsigned type_num,
		void (*constructor)(PMEMobjpool *pop, void *ptr, void *arg),
		void *arg)
{
	int ret = 0;

	TX_BEGIN(pop) {
		PMEMoid n = pmemobj_tx_alloc(size, type_num);
		constructor(pop, pmemobj_direct(n), arg);
		ctree_map_insert(pop, map, key, n);
	} TX_ONABORT {
		ret = 1;
	} TX_END

	return ret;
}

/*
 * ctree_map_insert -- inserts a new key-value pair into the map
 */
int
ctree_map_insert(PMEMobjpool *pop, TOID(struct ctree_map) map,
	uint64_t key, PMEMoid value)
{cpavise_tx_begin();

    // PAVISE_EDIT: example on how to time code segment
    //clock_t time_begin = clock();

	struct tree_map_entry *p = &D_RW(map)->root;
	int ret = 0;

	/* descend the path until a best matching key is found */
	TOID(struct tree_map_node) node;
    // PAVISE_EDIT. hardcoded pm pool root address. 
    // The new pmemobj_direct(p->slot)!=0x300003c0550 condition is equivalent to the original 
    // OID_INSTANCEOF(p->slot, struct tree_map_node) condition.
    // The pm pool root is tricky to obtain in this file.
    // The ctree_map and ctree_map->root are both not the pm pool root. 
    // The pm pool root is in map_bench.cpp as map_bench->root or map_bench->root_oid.
    // Unfortunately only map_bench->mapc->pop is passed into the ctree insert function.
    // Maybe we can use ctree's pop, which is the same as map_bench->mapc->pop, to get the pm pool root object?
    // Hardcoding the pm pool root address for now.
	while (!OID_IS_NULL(p->slot) && 
            pmemobj_direct(p->slot)!=0x300003c0550 ) { // exit if p->slot is the pm pool root (addr hardcoded)
	//while (!OID_IS_NULL(p->slot) &&
	//	OID_INSTANCEOF(p->slot, struct tree_map_node)) {
		TOID_ASSIGN(node, p->slot);
		p = &D_RW(node)->entries[BIT_IS_SET(key, D_RW(node)->diff)];
	}

	struct tree_map_entry e = {key, value};

	TX_BEGIN(pop) {
		if (p->key == 0 || p->key == key) {
			//pmemobj_tx_add_range_direct(p, sizeof(*p));//PAVISE_EDIT
			*p = e;
		} else {
			ctree_map_insert_leaf(&D_RW(map)->root, e,
					find_crit_bit(p->key, key));
		}
	} TX_ONABORT {
		ret = 1;
	} TX_END
    cpavise_tx_end(); //PAVISE_EDIT

    // PAVISE_EDIT: example on how to time code segment
    //clock_t time_end = clock();
    //time_spent_ctree_map_insert += (double)(time_end - time_begin) / CLOCKS_PER_SEC;
	//printf("total insert time: diff %d, time spent %f  \n", time_end - time_begin, time_spent_ctree_map_insert);

	return ret;
}

/*
 * ctree_map_get_leaf -- (internal) searches for a leaf of the key
 */
static struct tree_map_entry *
ctree_map_get_leaf(TOID(struct ctree_map) map, uint64_t key,
	struct tree_map_entry **parent)
{
	struct tree_map_entry *n = &D_RW(map)->root;
	struct tree_map_entry *p = NULL;

	TOID(struct tree_map_node) node;
	while (!OID_IS_NULL(n->slot) &&
				OID_INSTANCEOF(n->slot, struct tree_map_node)) {
		TOID_ASSIGN(node, n->slot);

		p = n;
		n = &D_RW(node)->entries[BIT_IS_SET(key, D_RW(node)->diff)];
	}

	if (n->key == key) {
		if (parent)
			*parent = p;

		return n;
	}

	return NULL;
}

/*
 * ctree_map_remove_free -- removes and frees an object from the tree
 */
int
ctree_map_remove_free(PMEMobjpool *pop, TOID(struct ctree_map) map,
		uint64_t key)
{
	int ret = 0;

	TX_BEGIN(pop) {
		PMEMoid val = ctree_map_remove(pop, map, key);
		pmemobj_tx_free(val);
	} TX_ONABORT {
		ret = 1;
	} TX_END

	return ret;
}

/*
 * ctree_map_remove -- removes key-value pair from the map
 */
PMEMoid
ctree_map_remove(PMEMobjpool *pop, TOID(struct ctree_map) map, uint64_t key)
{
	struct tree_map_entry *parent = NULL;
	struct tree_map_entry *leaf = ctree_map_get_leaf(map, key, &parent);
	if (leaf == NULL)
		return OID_NULL;

	PMEMoid ret = leaf->slot;

	if (parent == NULL) { /* root */
		TX_BEGIN(pop) {
			pmemobj_tx_add_range_direct(leaf, sizeof(*leaf));
			leaf->key = 0;
			leaf->slot = OID_NULL;
		} TX_END
	} else {
		/*
		 * In this situation:
		 *	 parent
		 *	/     \
		 *   LEFT   RIGHT
		 * there's no point in leaving the parent internal node
		 * so it's swapped with the remaining node and then also freed.
		 */
		TX_BEGIN(pop) {
			struct tree_map_entry *dest = parent;
			TOID(struct tree_map_node) node;
			TOID_ASSIGN(node, parent->slot);
			pmemobj_tx_add_range_direct(dest, sizeof(*dest));
			*dest = D_RW(node)->entries[
				D_RO(node)->entries[0].key == leaf->key];

			TX_FREE(node);
		} TX_END
	}

	return ret;
}

/*
 * ctree_map_get -- searches for a value of the key
 */
PMEMoid
ctree_map_get(PMEMobjpool *pop, TOID(struct ctree_map) map, uint64_t key)
{
	struct tree_map_entry *entry = ctree_map_get_leaf(map, key, NULL);
	return entry ? entry->slot : OID_NULL;
}

/*
 * ctree_map_lookup -- searches if a key exists
 */
int
ctree_map_lookup(PMEMobjpool *pop, TOID(struct ctree_map) map,
		uint64_t key)
{
	struct tree_map_entry *entry = ctree_map_get_leaf(map, key, NULL);
	return entry != NULL;
}

/*
 * ctree_map_foreach_node -- (internal) recursively traverses tree
 */
static int
ctree_map_foreach_node(struct tree_map_entry e,
	int (*cb)(uint64_t key, PMEMoid value, void *arg), void *arg)
{
	int ret = 0;

	if (OID_INSTANCEOF(e.slot, struct tree_map_node)) {
		TOID(struct tree_map_node) node;
		TOID_ASSIGN(node, e.slot);

		if (ctree_map_foreach_node(D_RO(node)->entries[0],
					cb, arg) == 0)
			ctree_map_foreach_node(D_RO(node)->entries[1], cb, arg);
	} else { /* leaf */
		ret = cb(e.key, e.slot, arg);
	}

	return ret;
}

/*
 * ctree_map_foreach -- initiates recursive traversal
 */
int
ctree_map_foreach(PMEMobjpool *pop, TOID(struct ctree_map) map,
	int (*cb)(uint64_t key, PMEMoid value, void *arg), void *arg)
{
	if (OID_IS_NULL(D_RO(map)->root.slot))
		return 0;

	return ctree_map_foreach_node(D_RO(map)->root, cb, arg);
}

/*
 * ctree_map_is_empty -- checks whether the tree map is empty
 */
int
ctree_map_is_empty(PMEMobjpool *pop, TOID(struct ctree_map) map)
{
	return D_RO(map)->root.key == 0;
}

/*
 * ctree_map_check -- check if given persistent object is a tree map
 */
int
ctree_map_check(PMEMobjpool *pop, TOID(struct ctree_map) map)
{
	return TOID_IS_NULL(map) || !TOID_VALID(map);
}
